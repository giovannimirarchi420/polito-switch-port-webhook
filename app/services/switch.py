"""
Switch port management service for configuring switch ports with VLANs.

This module handles network switch operations using netmiko to configure
individual switch ports with specific VLANs for switch port reservations.
"""
import logging
from typing import Optional

from netmiko import ConnectHandler, NetmikoTimeoutException, NetmikoAuthenticationException

from .. import config

logger = config.logger


class SwitchConfigurationError(Exception):
    """Raised when there's an error in switch configuration."""
    pass


class SwitchPortManager:
    """Manages switch port configurations for individual port reservations."""
    
    def __init__(self):
        """Initialize the SwitchPortManager."""
        self.logger = logger
        
        # Switch connection configuration
        self.switch_config = {
            "host": config.SWITCH_HOST,
            "username": config.SWITCH_USERNAME,
            "password": config.SWITCH_PASSWORD,
            "device_type": config.SWITCH_DEVICE_TYPE,
            "port": config.SWITCH_PORT,
            "timeout": config.SWITCH_TIMEOUT
        }
    
    def _connect_to_switch(self) -> ConnectHandler:
        """
        Establish connection to the network switch.
        
        Returns:
            Connected netmiko device instance
            
        Raises:
            SwitchConfigurationError: If connection fails
        """
        try:
            device = ConnectHandler(**self.switch_config)
            self.logger.info(f"Successfully connected to switch: {self.switch_config['host']}")
            return device
        except NetmikoTimeoutException as e:
            raise SwitchConfigurationError(f"Timeout connecting to switch: {e}")
        except NetmikoAuthenticationException as e:
            raise SwitchConfigurationError(f"Authentication failed for switch: {e}")
        except Exception as e:
            raise SwitchConfigurationError(f"Failed to connect to switch: {e}")
    
    def _create_or_verify_vlan(self, device: ConnectHandler, vlan_id: str, username: str) -> bool:
        """
        Create a VLAN with the given ID or verify it exists.
        
        Args:
            device: Connected netmiko device
            vlan_id: ID of the VLAN to create/verify
            username: Username for VLAN naming
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create or verify VLAN exists
            commands = [
                f"vlan {vlan_id}",
                f"name prognose-{username}-{vlan_id}",
                "exit"
            ]
            
            device.enable()  # Enter privileged mode
            output = device.send_config_set(commands)
            device.save_config()  # Save configuration
            
            self.logger.info(f"Created/verified VLAN '{vlan_id}' on switch")
            self.logger.debug(f"VLAN creation output: {output}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create/verify VLAN '{vlan_id}': {e}")
            return False
    
    def _find_available_vlan_id(self, device: ConnectHandler, start_id: int = 100) -> Optional[int]:
        """
        Find an available VLAN ID starting from the given ID.
        
        Args:
            device: Connected netmiko device
            start_id: Starting VLAN ID to search from
            
        Returns:
            Available VLAN ID or None if not found
        """
        try:
            show_vlan_output = device.send_command("show vlan brief")
            
            # Check VLAN IDs from start_id to 4094
            for vlan_id in range(start_id, 4095):
                if str(vlan_id) not in show_vlan_output:
                    return vlan_id
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding available VLAN ID: {e}")
            return None
    
    def _get_vlan_id_by_name(self, device: ConnectHandler, vlan_name: str) -> Optional[int]:
        """
        Get VLAN ID by name.
        
        Note: This method is kept for backward compatibility and potential future use.
        Currently, VLAN IDs are passed directly from custom parameters.
        
        Args:
            device: Connected netmiko device
            vlan_name: Name of the VLAN
            
        Returns:
            VLAN ID if found, None otherwise
        """
        try:
            show_vlan_output = device.send_command("show vlan brief")
            
            # Parse the output to find VLAN ID by name
            lines = show_vlan_output.split('\n')
            for line in lines:
                if vlan_name in line:
                    # Extract VLAN ID from the line
                    parts = line.split()
                    if parts and parts[0].isdigit():
                        return int(parts[0])
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting VLAN ID by name '{vlan_name}': {e}")
            return None
    
    def get_interfaces_using_vlan(self, vlan_id: str) -> list:
        """
        Get list of interfaces that are currently using the specified VLAN.
        
        Args:
            vlan_id: ID of the VLAN to check
            
        Returns:
            List of interface names using the VLAN, empty list if none found or error
        """
        try:
            device = self._connect_to_switch()
            
            try:
                # Get interfaces using this specific VLAN
                show_vlan_output = device.send_command(f"show vlan id {vlan_id}")
                
                # Check if VLAN doesn't exist
                if "not found in current VLAN database" in show_vlan_output:
                    self.logger.debug(f"VLAN ID '{vlan_id}' does not exist on switch")
                    return []
                
                # Parse the output to find interfaces for this VLAN
                lines = show_vlan_output.split('\n')
                interfaces = []
                
                # Look for the line containing the VLAN ID and ports
                for line in lines:
                    line = line.strip()
                    if line.startswith(str(vlan_id)):
                        # Split the line and get interface information
                        parts = line.split()
                        if len(parts) >= 4:
                            # The interfaces are typically in the 4th column and beyond
                            interface_part = ' '.join(parts[3:])
                            # Parse comma-separated interfaces
                            if interface_part.strip():
                                interface_names = [iface.strip() for iface in interface_part.split(',')]
                                interfaces.extend(interface_names)
                    elif line and not line.startswith(str(vlan_id)) and not line.startswith('VLAN') and not line.startswith('----'):
                        # This might be a continuation line with more interfaces
                        # Check if it looks like interface names
                        if any(keyword in line.lower() for keyword in ['gi', 'fa', 'eth', 'te', 'tw']):
                            interface_names = [iface.strip() for iface in line.split(',')]
                            interfaces.extend(interface_names)
                
                return interfaces
                
            finally:
                device.disconnect()
                
        except Exception as e:
            # If the VLAN doesn't exist, the command might fail - that's normal
            if "invalid" in str(e).lower() or "not found" in str(e).lower():
                self.logger.debug(f"VLAN ID '{vlan_id}' does not exist on switch")
                return []
            else:
                self.logger.error(f"Error getting interfaces using VLAN ID '{vlan_id}': {e}")
                return []
    
    def _assign_port_to_vlan(self, device: ConnectHandler, interface_name: str, vlan_id: str) -> bool:
        """
        Assign a switch port to a VLAN.
        
        Args:
            device: Connected netmiko device
            interface_name: Name of the interface to assign
            vlan_id: VLAN ID to assign port to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            commands = [
                f"interface {interface_name}",
                "switchport mode access",
                f"switchport access vlan {vlan_id}",
                "no shutdown",
                "exit"
            ]
            
            device.enable()  # Enter privileged mode
            output = device.send_config_set(commands)
            device.save_config()  # Save configuration
            
            self.logger.info(f"Assigned interface {interface_name} to VLAN {vlan_id}")
            self.logger.debug(f"Port assignment output: {output}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to assign interface {interface_name} to VLAN {vlan_id}: {e}")
            return False
    
    def configure_switch_port(self, interface_name: str, vlan_id: str, username: str) -> bool:
        """
        Configure a switch port with a specific VLAN.
        
        This method:
        1. Creates or verifies the VLAN exists
        2. Assigns the switch port to the VLAN
        3. Enables the port
        
        Args:
            interface_name: Name of the interface to configure
            vlan_id: ID of the VLAN to assign to the port
            username: Username for VLAN naming
            
        Returns:
            True if configuration was successful, False otherwise
        """
        if not interface_name or not vlan_id:
            self.logger.error("Interface name and VLAN ID are required")
            return False
        
        try:
            # Connect to switch
            device = self._connect_to_switch()
            
            try:
                # Create or verify VLAN exists
                if not self._create_or_verify_vlan(device, vlan_id, username):
                    return False
                
                # Assign port to VLAN
                if not self._assign_port_to_vlan(device, interface_name, vlan_id):
                    return False
                
                self.logger.info(
                    f"Successfully configured switch interface {interface_name} with VLAN ID '{vlan_id}'"
                )
                return True
                
            finally:
                device.disconnect()
                self.logger.info("Disconnected from switch")
                
        except SwitchConfigurationError as e:
            self.logger.error(f"Switch configuration error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during switch port configuration: {e}")
            return False
    
    def restore_port_to_default_vlan(self, interface_name: str) -> bool:
        """
        Restore a switch port to the default VLAN.
        
        Args:
            interface_name: Name of the interface to restore
            
        Returns:
            True if restoration was successful, False otherwise
        """
        if not interface_name:
            self.logger.error("Interface name is required")
            return False
        
        try:
            # Connect to switch
            device = self._connect_to_switch()
            
            try:
                # Assign port to default VLAN
                if not self._assign_port_to_vlan(device, interface_name, config.DEFAULT_VLAN_ID):
                    return False
                
                self.logger.info(
                    f"Successfully restored switch interface {interface_name} to default VLAN {config.DEFAULT_VLAN_ID}"
                )
                return True
                
            finally:
                device.disconnect()
                self.logger.info("Disconnected from switch")
                
        except SwitchConfigurationError as e:
            self.logger.error(f"Switch configuration error during port restoration: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during port restoration: {e}")
            return False


# Global instance for use in other modules
_switch_port_manager = None

def get_switch_port_manager() -> SwitchPortManager:
    """
    Get the global SwitchPortManager instance.
    
    Returns:
        SwitchPortManager instance
    """
    global _switch_port_manager
    if _switch_port_manager is None:
        _switch_port_manager = SwitchPortManager()
    return _switch_port_manager
