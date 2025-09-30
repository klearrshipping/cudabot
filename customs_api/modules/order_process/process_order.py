#!/usr/bin/env python3
"""
process_order.py
────────────────
Order Generation and Folder Organization Script

This script generates unique order numbers and creates the necessary folder structure
for organizing documents and processing results. It ensures all files are associated
with an order number at all times.

Usage:
    python process_order.py                    # Generate new order
    python process_order.py --list             # List existing orders
    python process_order.py <order_number>     # Show order details
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# Add the root directory to the path for imports
current_dir = Path(__file__).parent
root_dir = current_dir.parent.parent.parent
sys.path.insert(0, str(root_dir))

# Import database functions if available
try:
    from orders.models import create_order, get_order_by_number, get_all_orders
    from documents.models import get_documents_by_order
except ImportError:
    print("⚠️ Database models not available - running in file-only mode")
    create_order = None
    get_order_by_number = None
    get_all_orders = None
    get_documents_by_order = None


class OrderProcessor:
    """
    Order Generation and Folder Organization
    
    This class handles:
    - Generating unique order numbers
    - Creating folder structures for orders
    - Organizing documents and processing results
    - Ensuring all files are associated with order numbers
    """
    
    def __init__(self, base_dir: str = "processed_orders"):
        self.base_dir = Path(base_dir)
        
        # Create base directories if they don't exist
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Order Processor initialized
    
    def generate_order_number(self) -> str:
        """
        Generate a unique order number with format: ORD-YYYYMMDD-XXX
        
        Returns:
            str: Unique order number
        """
        today = datetime.now()
        date_prefix = today.strftime("%Y%m%d")
        
        # Find the next available sequence number for today
        sequence = 1
        while True:
            order_number = f"ORD-{date_prefix}-{sequence:03d}"
            
            # Check if order number already exists
            if not self._order_exists(order_number):
                return order_number
            
            sequence += 1
    
    def _order_exists(self, order_number: str) -> bool:
        """
        Check if an order number already exists
        
        Args:
            order_number (str): Order number to check
            
        Returns:
            bool: True if order exists, False otherwise
        """
        # Check database first
        if get_order_by_number:
            try:
                order = get_order_by_number(order_number)
                if order:
                    return True
            except:
                pass
        
        # Check file system
        order_dir = self.base_dir / order_number
        return order_dir.exists()
    
    def create_order(self, description: str = None, client_name: str = None) -> Dict[str, Any]:
        """
        Create a new order with unique order number and folder structure
        
        Args:
            description (str): Optional description for the order
            client_name (str): Optional client name
            
        Returns:
            dict: Order creation results
        """
        # Creating new order
        
        # Generate unique order number
        order_number = self.generate_order_number()
        # Generated order number
        
        # Create order directory structure
        order_dir = self.base_dir / order_number
        
        # Create all necessary subdirectories
        directories = {
            'order_root': order_dir,
            'file_uploads': order_dir / "file_uploads",
            'invoices': order_dir / "invoices",
            'bills_of_lading': order_dir / "bills_of_lading",
            'esad_files': order_dir / "esad_files",
            'commodity_code': order_dir / "commodity_code"
        }
        
        for name, path in directories.items():
            path.mkdir(parents=True, exist_ok=True)
            # Created directory
        
        # Create order metadata file
        order_metadata = {
            'order_number': order_number,
            'created_at': datetime.now().isoformat(),
            'status': 'created',
            'description': description or f"Order created on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            'client_name': client_name or 'Unknown',
            'directories': {name: str(path) for name, path in directories.items()},
            'files': {
                'file_uploads': [],
                'invoices': [],
                'bills_of_lading': [],
                'esad_files': [],
                'commodity_code': []
            },
            'processing_status': {
                'files_uploaded': False,
                'invoices_processed': False,
                'bills_processed': False,
                'esad_processed': False,
                'completed': False
            }
        }
        
        # Save metadata
        metadata_file = order_dir / "order_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(order_metadata, f, indent=2, ensure_ascii=False)
        
        # Created order_metadata.json
        
        # Create database record if available
        if create_order:
            try:
                db_order = create_order(
                    order_number=order_number,
                    description=description or f"Auto-generated order {order_number}",
                    client_name=client_name or 'Unknown',
                    status='created'
                )
                print(f"   💾 Saved to database: Order ID {db_order.get('id', 'N/A')}")
            except Exception as e:
                print(f"   ⚠️ Database save failed: {e}")
        
        print(f"✅ Order {order_number} created successfully!")
        
        return {
            'status': 'success',
            'order_number': order_number,
            'order_directory': str(order_dir),
            'metadata_file': str(metadata_file),
            'created_at': order_metadata['created_at']
        }
    
    def get_order_info(self, order_number: str) -> Dict[str, Any]:
        """
        Get information about an existing order
        
        Args:
            order_number (str): Order number to look up
            
        Returns:
            dict: Order information
        """
        if not self._order_exists(order_number):
            return {'error': f'Order {order_number} not found'}
        
        order_dir = self.base_dir / order_number
        
        # Load metadata
        metadata_file = order_dir / "order_metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        else:
            metadata = {
                'order_number': order_number,
                'status': 'unknown',
                'created_at': 'unknown',
                'description': 'No metadata available'
            }
        
        # Get file counts
        file_counts = self._count_files_in_order(order_number)
        
        # Get database info if available
        db_info = {}
        if get_order_by_number:
            try:
                db_order = get_order_by_number(order_number)
                if db_order:
                    db_info = {
                        'database_id': db_order.get('id'),
                        'db_status': db_order.get('status'),
                        'db_created_at': db_order.get('created_at')
                    }
            except:
                pass
        
        return {
            'order_number': order_number,
            'order_directory': str(order_dir),
            'metadata': metadata,
            'file_counts': file_counts,
            'database_info': db_info,
            'exists': True
        }
    
    def _count_files_in_order(self, order_number: str) -> Dict[str, int]:
        """
        Count files in each directory of an order
        
        Args:
            order_number (str): Order number
            
        Returns:
            dict: File counts by directory
        """
        order_dir = self.base_dir / order_number
        counts = {}
        
        directories = [
            'file_uploads', 'invoices', 'bills_of_lading', 'esad_files'
        ]
        
        for dir_name in directories:
            dir_path = order_dir / dir_name
            if dir_path.exists():
                counts[dir_name] = len(list(dir_path.glob('*')))
            else:
                counts[dir_name] = 0
        
        return counts
    
    def list_orders(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        List all existing orders
        
        Args:
            limit (int): Maximum number of orders to return
            
        Returns:
            list: List of order information
        """
        orders = []
        
        # Get from database if available
        if get_all_orders:
            try:
                db_orders = get_all_orders(limit=limit)
                for db_order in db_orders:
                    order_info = self.get_order_info(db_order['order_number'])
                    order_info['database_info'] = {
                        'id': db_order.get('id'),
                        'status': db_order.get('status'),
                        'created_at': db_order.get('created_at')
                    }
                    orders.append(order_info)
                return orders
            except:
                pass
        
        # Fallback to file system scan
        if self.base_dir.exists():
            order_dirs = sorted([d for d in self.base_dir.iterdir() if d.is_dir()], 
                              key=lambda x: x.name, reverse=True)
            
            for order_dir in order_dirs[:limit]:
                order_number = order_dir.name
                order_info = self.get_order_info(order_number)
                if 'error' not in order_info:
                    orders.append(order_info)
        
        return orders
    
    def associate_file_with_order(self, order_number: str, file_path: str, 
                                 file_type: str = 'document') -> Dict[str, Any]:
        """
        Associate a file with an order and update metadata
        
        Args:
            order_number (str): Order number
            file_path (str): Path to the file
            file_type (str): Type of file (document, extract, esad_field, etc.)
            
        Returns:
            dict: Association results
        """
        if not self._order_exists(order_number):
            return {'error': f'Order {order_number} not found'}
        
        order_dir = self.base_dir / order_number
        metadata_file = order_dir / "order_metadata.json"
        
        # Load current metadata
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
        else:
            return {'error': 'Order metadata not found'}
        
        # Add file to appropriate category
        file_path_obj = Path(file_path)
        relative_path = str(file_path_obj.relative_to(order_dir)) if file_path_obj.is_relative_to(order_dir) else str(file_path_obj)
        
        if file_type == 'file_upload':
            metadata['files']['file_uploads'].append(relative_path)
        elif file_type == 'invoice':
            metadata['files']['invoices'].append(relative_path)
        elif file_type == 'bill_of_lading':
            metadata['files']['bills_of_lading'].append(relative_path)
        elif file_type == 'esad_file':
            metadata['files']['esad_files'].append(relative_path)
        
        # Update metadata
        metadata['updated_at'] = datetime.now().isoformat()
        
        # Save updated metadata
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        return {
            'status': 'success',
            'order_number': order_number,
            'file_path': relative_path,
            'file_type': file_type,
            'associated_at': datetime.now().isoformat()
        }
    
    def add_file_to_order_metadata(self, order_number: str, file_path: str, document_type: str) -> Dict[str, Any]:
        """
        Add file to order metadata (alias for associate_file_with_order)
        
        Args:
            order_number (str): Order number
            file_path (str): Path to the file
            document_type (str): Type of document
            
        Returns:
            dict: Association results
        """
        return self.associate_file_with_order(order_number, file_path, document_type)


def main():
    """Main function for command line usage"""
    if len(sys.argv) == 1:
        # Generate new order
        processor = OrderProcessor()
        result = processor.create_order()
        
        if result['status'] == 'success':
            print(f"\n🎉 New Order Created Successfully!")
            print(f"   Order Number: {result['order_number']}")
            print(f"   Created: {result['created_at']}")
            print(f"\n📁 Next Steps:")
            print(f"   1. Upload documents to: {result['order_directory']}/file_uploads/")
            print(f"   2. Run document processing on order: {result['order_number']}")
            print(f"   3. Check status with: python process_order.py {result['order_number']}")
        else:
            print(f"❌ Order creation failed: {result.get('error', 'Unknown error')}")
    
    elif len(sys.argv) == 2:
        if sys.argv[1] == '--list':
            # List all orders
            processor = OrderProcessor()
            orders = processor.list_orders()
            
            print(f"\n📋 Existing Orders ({len(orders)} found):")
            print("=" * 80)
            
            for order in orders:
                print(f"📦 {order['order_number']}")
                print(f"   Created: {order['metadata'].get('created_at', 'Unknown')}")
                print(f"   Status: {order['metadata'].get('status', 'Unknown')}")
                print(f"   Description: {order['metadata'].get('description', 'No description')}")
                
                # Show file counts
                counts = order['file_counts']
                print(f"   Files: {counts['file_uploads']} uploaded, {counts['invoices']} invoices, {counts['bills_of_lading']} bills, {counts['esad_files']} esad")
                print()
        else:
            # Show order details
            order_number = sys.argv[1]
            processor = OrderProcessor()
            order_info = processor.get_order_info(order_number)
            
            if 'error' in order_info:
                print(f"❌ {order_info['error']}")
            else:
                print(f"\n📦 Order Details: {order_number}")
                print("=" * 60)
                print(f"Created: {order_info['metadata'].get('created_at', 'Unknown')}")
                print(f"Status: {order_info['metadata'].get('status', 'Unknown')}")
                print(f"Description: {order_info['metadata'].get('description', 'No description')}")
                print(f"Client: {order_info['metadata'].get('client_name', 'Unknown')}")
                
                print(f"\n📁 Directory Structure:")
                for dir_name, count in order_info['file_counts'].items():
                    print(f"   {dir_name}: {count} files")
                
                print(f"\n📂 Order Directory: {order_info['order_directory']}")
    
    else:
        print("Usage:")
        print("  python process_order.py                    # Generate new order")
        print("  python process_order.py --list             # List existing orders")
        print("  python process_order.py <order_number>     # Show order details")


if __name__ == "__main__":
    main()
