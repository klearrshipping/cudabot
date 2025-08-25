#!/usr/bin/env python3
"""
Delete utility script for CUDA project
Handles cleanup of orders, processed data, temporary files, and Supabase database
"""

import os
import shutil
import subprocess
from pathlib import Path

# Try to import Supabase client for database operations
try:
    from config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("⚠️ Supabase integration not available")

def force_delete_directory(path: str):
    """Force delete a directory using PowerShell Remove-Item with -Force flag"""
    try:
        if os.path.exists(path):
            # Use PowerShell Remove-Item with -Force for stubborn directories
            cmd = f'Remove-Item -Path "{path}" -Recurse -Force'
            result = subprocess.run(['powershell', '-Command', cmd], 
                                  capture_output=True, text=True, shell=True)
            
            if result.returncode == 0:
                print(f"✅ Force deleted: {path}")
                return True
            else:
                print(f"⚠️ PowerShell failed: {result.stderr}")
                return False
        else:
            print(f"⚠️ Not found: {path}")
            return False
            
    except Exception as e:
        print(f"❌ Error force deleting {path}: {e}")
        return False

def delete_order(order_id: str):
    """Delete a specific order and all its associated data"""
    try:
        # Paths to check and delete
        order_paths = [
            f"processed_data/orders/{order_id}",
            f"orders/{order_id}",
            f"uploads/{order_id}"
        ]
        
        for path in order_paths:
            if os.path.exists(path):
                # Try normal deletion first
                try:
                    shutil.rmtree(path)
                    print(f"✅ Deleted: {path}")
                except PermissionError:
                    # If permission denied, use force deletion
                    print(f"🔄 Permission denied, trying force deletion for: {path}")
                    force_delete_directory(path)
                except Exception as e:
                    print(f"❌ Error deleting {path}: {e}")
            else:
                print(f"⚠️ Not found: {path}")
                
    except Exception as e:
        print(f"❌ Error deleting order {order_id}: {e}")

def cleanup_temp_files():
    """Clean up temporary and cache files"""
    try:
        # Remove Python cache
        if os.path.exists("__pycache__"):
            try:
                shutil.rmtree("__pycache__")
                print("✅ Cleaned: __pycache__")
            except PermissionError:
                print(f"🔄 Permission denied, trying force deletion for: __pycache__")
                force_delete_directory("__pycache__")
            
        # Remove other temp directories if empty
        temp_dirs = ["temp", "temp_processing_output"]
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                try:
                    if not os.listdir(temp_dir):
                        os.rmdir(temp_dir)
                        print(f"✅ Cleaned: {temp_dir}")
                    else:
                        # Directory not empty, try force deletion
                        print(f"🔄 Directory not empty, trying force deletion for: {temp_dir}")
                        force_delete_directory(temp_dir)
                except PermissionError:
                    print(f"🔄 Permission denied, trying force deletion for: {temp_dir}")
                    force_delete_directory(temp_dir)
                
    except Exception as e:
        print(f"❌ Error cleaning temp files: {e}")

def cleanup_supabase_data():
    """Clean up all order-related data from Supabase database"""
    if not SUPABASE_AVAILABLE:
        print("⚠️ Supabase not available - skipping database cleanup")
        return
    
    try:
        # Initialize Supabase client with service role key
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        print("✅ Connected to Supabase for cleanup")
        
        # Delete all records from esad_fields table
        try:
            result = supabase.table("esad_fields").delete().neq("id", 0).execute()
            deleted_count = len(result.data) if result.data else 0
            print(f"✅ Deleted {deleted_count} records from esad_fields table")
        except Exception as e:
            print(f"⚠️ Error cleaning esad_fields table: {e}")
        
        # Delete all records from orders table (if it exists)
        try:
            result = supabase.table("orders").delete().neq("id", 0).execute()
            deleted_count = len(result.data) if result.data else 0
            print(f"✅ Deleted {deleted_count} records from orders table")
        except Exception as e:
            print(f"⚠️ Error cleaning orders table: {e}")
        
        # Delete all records from processed_data table (if it exists)
        try:
            result = supabase.table("processed_data").delete().neq("id", 0).execute()
            deleted_count = len(result.data) if result.data else 0
            print(f"✅ Deleted {deleted_count} records from processed_data table")
        except Exception as e:
            print(f"⚠️ Error cleaning processed_data table: {e}")
            
    except Exception as e:
        print(f"❌ Error connecting to Supabase: {e}")

def main():
    """Main cleanup function"""
    print("🧹 CUDA Project Cleanup Utility")
    print("=" * 40)
    
    # First, remove any orders that were created
    print("🗑️ Removing created orders and associated files...")
    
    # Check for orders in processed_data/orders
    orders_dir = "processed_data/orders"
    if os.path.exists(orders_dir):
        for order_folder in os.listdir(orders_dir):
            order_path = os.path.join(orders_dir, order_folder)
            try:
                shutil.rmtree(order_path)
                print(f"✅ Deleted order: {order_folder}")
            except PermissionError:
                print(f"🔄 Permission denied, trying force deletion for: {order_folder}")
                force_delete_directory(order_path)
            except Exception as e:
                print(f"❌ Error deleting {order_folder}: {e}")
    
    # Check for orders in orders directory
    if os.path.exists("orders"):
        for order_folder in os.listdir("orders"):
            order_path = os.path.join("orders", order_folder)
            try:
                shutil.rmtree(order_path)
                print(f"✅ Deleted order: {order_folder}")
            except PermissionError:
                print(f"🔄 Permission denied, trying force deletion for: {order_folder}")
                force_delete_directory(order_path)
            except Exception as e:
                print(f"❌ Error deleting {order_folder}: {e}")
    
    # Check for orders in uploads directory
    if os.path.exists("uploads"):
        for order_folder in os.listdir("uploads"):
            order_path = os.path.join("uploads", order_folder)
            try:
                shutil.rmtree(order_path)
                print(f"✅ Deleted order: {order_folder}")
            except PermissionError:
                print(f"🔄 Permission denied, trying force deletion for: {order_folder}")
                force_delete_directory(order_path)
            except Exception as e:
                print(f"❌ Error deleting {order_folder}: {e}")
    
    # Then clean up Supabase database
    print("\n🗄️ Cleaning up Supabase database...")
    cleanup_supabase_data()
    
    # Finally clean up temp files
    print("\n🧹 Cleaning up temporary files...")
    cleanup_temp_files()
    
    print("\n✅ Cleanup completed!")

if __name__ == "__main__":
    main()
