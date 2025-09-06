#!/usr/bin/env python3
"""
eSAD Reference Number Processor
Processes commercial reference numbers using order IDs from our system
"""

import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import os

@dataclass
class ReferenceNumberConfig:
    """Configuration for reference number generation"""
    prefix: str
    start_number: int
    padding: int
    separator: str
    description: str
    created_at: str
    last_used: Optional[str] = None

@dataclass
class ReferenceNumberResult:
    """Result of reference number generation"""
    reference_id: str
    config_used: str
    generation_time: str
    sequence_number: int
    success: bool
    error_message: Optional[str] = None

class CommercialReferenceProcessor:
    """Processes commercial reference numbers using order IDs"""
    
    def __init__(self, config_file: str = "ref_number_config.json"):
        """Initialize the commercial reference processor"""
        self.config_file = Path(config_file)
        self.configs: Dict[str, ReferenceNumberConfig] = {}
        self.load_configs()
    
    def load_configs(self) -> None:
        """Load existing reference number configurations"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                for config_name, config_dict in config_data.items():
                    self.configs[config_name] = ReferenceNumberConfig(
                        prefix=config_dict['prefix'],
                        start_number=config_dict['start_number'],
                        padding=config_dict['padding'],
                        separator=config_dict['separator'],
                        description=config_dict['description'],
                        created_at=config_dict['created_at'],
                        last_used=config_dict.get('last_used')
                    )
                
                print(f"✅ Loaded {len(self.configs)} reference number configurations")
                
            except Exception as e:
                print(f"❌ Error loading configurations: {e}")
                self.configs = {}
        else:
            print("📝 No existing configuration file found, starting fresh")
            self.configs = {}
    
    def save_configs(self) -> None:
        """Save reference number configurations to file"""
        try:
            config_data = {}
            for config_name, config in self.configs.items():
                config_data[config_name] = {
                    'prefix': config.prefix,
                    'start_number': config.start_number,
                    'padding': config.padding,
                    'separator': config.separator,
                    'description': config.description,
                    'created_at': config.created_at,
                    'last_used': config.last_used
                }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Saved {len(self.configs)} configurations to {self.config_file}")
            
        except Exception as e:
            print(f"❌ Error saving configurations: {e}")
    
    def create_config(self, name: str, prefix: str, start_number: int = 1, 
                     padding: int = 4, separator: str = "-") -> bool:
        """Create a new reference number configuration"""
        try:
            # Validate inputs
            if not name or not prefix:
                print("❌ Name and prefix are required")
                return False
            
            if name in self.configs:
                print(f"❌ Configuration '{name}' already exists")
                return False
            
            # Create new configuration
            config = ReferenceNumberConfig(
                prefix=prefix.upper(),
                start_number=start_number,
                padding=padding,
                separator=separator,
                description=f"Custom configuration for {prefix}",
                created_at=datetime.now().isoformat()
            )
            
            self.configs[name] = config
            self.save_configs()
            
            print(f"✅ Created configuration '{name}' with prefix '{prefix}'")
            return True
            
        except Exception as e:
            print(f"❌ Error creating configuration: {e}")
            return False
    
    def process_commercial_reference(self, order_id: int, config_name: str = "default") -> str:
        """
        Process commercial reference number using order ID
        
        Args:
            order_id: The order ID from our system
            config_name: Configuration to use (defaults to 'default')
            
        Returns:
            Processed commercial reference number
        """
        try:
            # If no configs exist, create a default one
            if not self.configs:
                self._create_default_config()
            
            # Use specified config or default
            if config_name not in self.configs:
                print(f"⚠️ Configuration '{config_name}' not found, using 'default'")
                config_name = "default"
            
            config = self.configs[config_name]
            
            # Generate reference number using order ID
            reference_number = self._generate_reference_from_order_id(order_id, config)
            
            # Update last used timestamp
            config.last_used = datetime.now().isoformat()
            self.save_configs()
            
            print(f"✅ Generated commercial reference: {reference_number} for order {order_id}")
            return reference_number
            
        except Exception as e:
            print(f"❌ Error processing commercial reference: {e}")
            # Fallback: return order ID as string
            return f"ORD-{order_id}"
    
    def _create_default_config(self) -> None:
        """Create a default configuration if none exists"""
        default_config = ReferenceNumberConfig(
            prefix="ORD",
            start_number=1,
            padding=6,
            separator="-",
            description="Default order reference configuration",
            created_at=datetime.now().isoformat()
        )
        
        self.configs["default"] = default_config
        self.save_configs()
        print("✅ Created default configuration")
    
    def _generate_reference_from_order_id(self, order_id: int, config: ReferenceNumberConfig) -> str:
        """Generate reference number from order ID using configuration"""
        # Use the order ID as the sequence number
        sequence_number = order_id
        
        # Format the reference number
        formatted_sequence = str(sequence_number).zfill(config.padding)
        reference_number = f"{config.prefix}{config.separator}{formatted_sequence}"
        
        return reference_number
    
    def get_next_number(self, config_name: str) -> Optional[ReferenceNumberResult]:
        """Get next reference number for a configuration (legacy function)"""
        try:
            if config_name not in self.configs:
                print(f"❌ Configuration '{config_name}' not found")
                return None
            
            config = self.configs[config_name]
            
            # Determine next sequence number
            if config.last_used:
                # Parse last used to get sequence
                last_used = datetime.fromisoformat(config.last_used)
                # For now, just increment by 1
                next_sequence = config.start_number + 1
            else:
                next_sequence = config.start_number
            
            # Generate reference number
            formatted_sequence = str(next_sequence).zfill(config.padding)
            reference_id = f"{config.prefix}{config.separator}{formatted_sequence}"
            
            result = ReferenceNumberResult(
                reference_id=reference_id,
                config_used=config_name,
                generation_time=datetime.now().isoformat(),
                sequence_number=next_sequence,
                success=True
            )
            
            # Update last used
            config.last_used = datetime.now().isoformat()
            self.save_configs()
            
            return result
            
        except Exception as e:
            print(f"❌ Error generating next number: {e}")
            return None
    
    def list_configs(self) -> None:
        """List all available configurations"""
        if not self.configs:
            print("📝 No configurations available")
            return
        
        print(f"\n📋 AVAILABLE CONFIGURATIONS ({len(self.configs)}):")
        for name, config in self.configs.items():
            last_used = config.last_used or "Never"
            print(f"  {name}:")
            print(f"    Prefix: {config.prefix}")
            print(f"    Start: {config.start_number}")
            print(f"    Padding: {config.padding}")
            print(f"    Separator: '{config.separator}'")
            print(f"    Last Used: {last_used}")
            print(f"    Created: {config.created_at}")
            print()
    
    def delete_config(self, name: str) -> bool:
        """Delete a configuration"""
        try:
            if name not in self.configs:
                print(f"❌ Configuration '{name}' not found")
                return False
            
            del self.configs[name]
            self.save_configs()
            print(f"✅ Deleted configuration '{name}'")
            return True
            
        except Exception as e:
            print(f"❌ Error deleting configuration: {e}")
            return False
    
    def reset_config(self, name: str) -> bool:
        """Reset a configuration to its original state"""
        try:
            if name not in self.configs:
                print(f"❌ Configuration '{name}' not found")
                return False
            
            config = self.configs[name]
            config.last_used = None
            self.save_configs()
            
            print(f"✅ Reset configuration '{name}'")
            return True
            
        except Exception as e:
            print(f"❌ Error resetting configuration: {e}")
            return False
    
    def save_reference_result(self, result: ReferenceNumberResult) -> str:
        """Save reference number result to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"reference_result_{timestamp}.json"
        
        result_data = {
            'reference_id': result.reference_id,
            'config_used': result.config_used,
            'generation_time': result.generation_time,
            'sequence_number': result.sequence_number,
            'success': result.success,
            'error_message': result.error_message
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Reference number result saved to: {output_file}")
        return output_file

def main():
    """Interactive reference number generator"""
    print("=== eSAD COMMERCIAL REFERENCE PROCESSOR ===\n")
    
    # Initialize processor
    processor = CommercialReferenceProcessor()
    
    while True:
        print("\n🔧 COMMERCIAL REFERENCE PROCESSOR MENU:")
        print("1. List configurations")
        print("2. Create new configuration")
        print("3. Process commercial reference (using order ID)")
        print("4. Generate next reference number")
        print("5. Delete configuration")
        print("6. Reset configuration")
        print("7. Exit")
        
        choice = input("\nEnter your choice (1-7): ").strip()
        
        if choice == "1":
            processor.list_configs()
            
        elif choice == "2":
            print("\n📝 CREATE NEW CONFIGURATION:")
            name = input("Configuration name: ").strip()
            prefix = input("Prefix (e.g., ORD, KFTL): ").strip()
            start_number = input("Start number (default 1): ").strip()
            padding = input("Padding digits (default 6): ").strip()
            separator = input("Separator (default -): ").strip()
            
            # Set defaults
            start_number = int(start_number) if start_number.isdigit() else 1
            padding = int(padding) if padding.isdigit() else 6
            separator = separator if separator else "-"
            
            processor.create_config(name, prefix, start_number, padding, separator)
            
        elif choice == "3":
            print("\n🎯 PROCESS COMMERCIAL REFERENCE:")
            order_id_input = input("Enter order ID: ").strip()
            
            if order_id_input.isdigit():
                order_id = int(order_id_input)
                processor.list_configs()
                
                if processor.configs:
                    config_name = input("Enter configuration name (or press Enter for default): ").strip()
                    if not config_name:
                        config_name = "default"
                    
                    reference_number = processor.process_commercial_reference(order_id, config_name)
                    print(f"\n📊 COMMERCIAL REFERENCE PROCESSED:")
                    print(f"   Order ID: {order_id}")
                    print(f"   Reference Number: {reference_number}")
                else:
                    print("❌ No configurations available. Create one first.")
            else:
                print("❌ Invalid order ID. Please enter a number.")
                
        elif choice == "4":
            print("\n🎯 GENERATE NEXT REFERENCE NUMBER:")
            processor.list_configs()
            
            if processor.configs:
                config_name = input("Enter configuration name: ").strip()
                result = processor.get_next_number(config_name)
                
                if result and result.success:
                    output_file = processor.save_reference_result(result)
                    
                    print(f"\n📊 REFERENCE NUMBER GENERATED:")
                    print(f"   Reference ID: {result.reference_id}")
                    print(f"   Configuration: {result.config_used}")
                    print(f"   Sequence Number: {result.sequence_number}")
                    print(f"   Generated At: {result.generation_time}")
                else:
                    print("❌ Failed to generate reference number")
            else:
                print("❌ No configurations available. Create one first.")
                
        elif choice == "5":
            print("\n🗑️ DELETE CONFIGURATION:")
            processor.list_configs()
            
            if processor.configs:
                config_name = input("Enter configuration name to delete: ").strip()
                confirm = input(f"Are you sure you want to delete '{config_name}'? (y/N): ").strip().lower()
                
                if confirm == 'y':
                    processor.delete_config(config_name)
                else:
                    print("❌ Deletion cancelled")
            else:
                print("❌ No configurations to delete")
                
        elif choice == "6":
            print("\n🔄 RESET CONFIGURATION:")
            processor.list_configs()
            
            if processor.configs:
                config_name = input("Enter configuration name to reset: ").strip()
                confirm = input(f"Are you sure you want to reset '{config_name}'? (y/N): ").strip().lower()
                
                if confirm == 'y':
                    processor.reset_config(config_name)
                else:
                    print("❌ Reset cancelled")
            else:
                print("❌ No configurations to delete")
                
        elif choice == "7":
            print("👋 Goodbye!")
            break
            
        else:
            print("❌ Invalid choice. Please enter 1-7.")

if __name__ == "__main__":
    main() 