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
    
    def _create_or_verify_vlan(self, device: ConnectHandler, vlan_name: str) -> bool:
        """
        Create a VLAN with the given name or verify it exists.
        
        Args:
            device: Connected netmiko device
            vlan_name: Name of the VLAN to create/verify
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if VLAN already exists by name
            show_vlan_output = device.send_command("show vlan brief")
            
            # Look for the VLAN name in the output
            if vlan_name in show_vlan_output:
                self.logger.info(f"VLAN '{vlan_name}' already exists on switch")
                return True
            
            # VLAN doesn't exist, create it
            # For now, we'll use a simple VLAN ID assignment strategy
            # In a production environment, you might want more sophisticated VLAN ID management
            
            # Find an available VLAN ID (starting from 100)
            vlan_id = self._find_available_vlan_id(device)
            if not vlan_id:
                self.logger.error("No available VLAN ID found")
                return False
            
            commands = [
                f"vlan {vlan_id}",
                f"name {vlan_name}",
                f"description Auto-created VLAN for switch port reservation",
                "exit"
            ]
            
            device.enable()  # Enter privileged mode
            output = device.send_config_set(commands)
            device.save_config()  # Save configuration
            
            self.logger.info(f"Created VLAN {vlan_id} with name '{vlan_name}' on switch")
            self.logger.debug(f"VLAN creation output: {output}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create/verify VLAN '{vlan_name}': {e}")
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
    
    def _assign_port_to_vlan(self, device: ConnectHandler, port_number: int, vlan_id: int) -> bool:
        """
        Assign a switch port to a VLAN.
        
        Args:
            device: Connected netmiko device
            port_number: Port number to assign
            vlan_id: VLAN ID to assign port to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            interface_name = f"Twe1/0/{port_number}"
            
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
            
            self.logger.info(f"Assigned port {port_number} to VLAN {vlan_id}")
            self.logger.debug(f"Port assignment output: {output}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to assign port {port_number} to VLAN {vlan_id}: {e}")
            return False
    
    def configure_switch_port(self, port_number: int, vlan_name: str) -> bool:
        """
        Configure a switch port with a specific VLAN.
        
        This method:
        1. Creates or verifies the VLAN exists
        2. Assigns the switch port to the VLAN
        3. Enables the port
        
        Args:
            port_number: Switch port number to configure
            vlan_name: Name of the VLAN to assign to the port
            
        Returns:
            True if configuration was successful, False otherwise
        """
        if not port_number or not vlan_name:
            self.logger.error("Port number and VLAN name are required")
            return False
        
        try:
            # Connect to switch
            device = self._connect_to_switch()
            
            try:
                # Create or verify VLAN exists
                if not self._create_or_verify_vlan(device, vlan_name):
                    return False
                
                # Get VLAN ID by name
                vlan_id = self._get_vlan_id_by_name(device, vlan_name)
                if not vlan_id:
                    self.logger.error(f"Could not find VLAN ID for VLAN name '{vlan_name}'")
                    return False
                
                # Assign port to VLAN
                if not self._assign_port_to_vlan(device, port_number, vlan_id):
                    return False
                
                self.logger.info(
                    f"Successfully configured switch port {port_number} with VLAN '{vlan_name}' (ID: {vlan_id})"
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
    
    def restore_port_to_default_vlan(self, port_number: int) -> bool:
        """
        Restore a switch port to the default VLAN.
        
        Args:
            port_number: Port number to restore
            
        Returns:
            True if restoration was successful, False otherwise
        """
        if not port_number:
            self.logger.error("Port number is required")
            return False
        
        try:
            # Connect to switch
            device = self._connect_to_switch()
            
            try:
                # Assign port to default VLAN
                if not self._assign_port_to_vlan(device, port_number, config.DEFAULT_VLAN_ID):
                    return False
                
                self.logger.info(
                    f"Successfully restored switch port {port_number} to default VLAN {config.DEFAULT_VLAN_ID}"
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
