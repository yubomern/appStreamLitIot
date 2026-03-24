import streamlit as st
import pandas as pd
import sqlite3
import os
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io
import base64
import json
import numpy as np

# ============================================================================
# Database Setup
# ============================================================================

DB_FILE = "products.db"

def init_db():
    """Initialize database with all required tables"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Categories table
    c.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Products table
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_number TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category_id INTEGER,
            description TEXT,
            price REAL,
            quantity INTEGER,
            unit TEXT,
            supplier TEXT,
            min_quantity INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE SET NULL
        )
    ''')
    
    # Stock movements table
    c.execute('''
        CREATE TABLE IF NOT EXISTS stock_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            movement_type TEXT,
            quantity INTEGER,
            previous_quantity INTEGER,
            new_quantity INTEGER,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
        )
    ''')
    
    # Insert default categories if empty
    c.execute("SELECT COUNT(*) FROM categories")
    if c.fetchone()[0] == 0:
        default_categories = [
            ('Electronics', 'Electronic devices and components'),
            ('Clothing', 'Apparel and accessories'),
            ('Food', 'Food and beverage items'),
            ('Furniture', 'Home and office furniture'),
            ('Tools', 'Tools and equipment'),
            ('Other', 'Miscellaneous items')
        ]
        c.executemany("INSERT INTO categories (name, description) VALUES (?, ?)", default_categories)
    
    conn.commit()
    conn.close()

init_db()

# ============================================================================
# Database Functions
# ============================================================================

# Category functions
def add_category(name, description):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("INSERT INTO categories (name, description) VALUES (?, ?)", (name, description))
        conn.commit()
        conn.close()
        return True, "Category added successfully"
    except sqlite3.IntegrityError:
        return False, "Category name already exists"

def get_categories():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM categories ORDER BY name", conn)
    conn.close()
    return df

def update_category(category_id, name, description):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE categories SET name=?, description=? WHERE id=?", (name, description, category_id))
    conn.commit()
    conn.close()

def delete_category(category_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM categories WHERE id=?", (category_id,))
    conn.commit()
    conn.close()

# Product functions
def add_product(product_number, name, category_id, description, price, quantity, unit, supplier, min_quantity):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT INTO products 
            (product_number, name, category_id, description, price, quantity, unit, supplier, min_quantity)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (product_number, name, category_id, description, price, quantity, unit, supplier, min_quantity))
        
        product_id = c.lastrowid
        
        # Log initial stock movement
        c.execute('''
            INSERT INTO stock_movements 
            (product_id, movement_type, quantity, previous_quantity, new_quantity, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (product_id, 'INITIAL', quantity, 0, quantity, 'Initial stock'))
        
        conn.commit()
        conn.close()
        return True, "Product added successfully"
    except sqlite3.IntegrityError:
        return False, "Product number already exists"

def get_products(filter_category=None, search_term=None):
    conn = sqlite3.connect(DB_FILE)
    query = '''
        SELECT p.*, c.name as category_name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE 1=1
    '''
    params = []
    
    if filter_category and filter_category != 'All':
        query += " AND p.category_id = ?"
        params.append(filter_category)
    
    if search_term:
        query += " AND (p.product_number LIKE ? OR p.name LIKE ? OR p.description LIKE ?)"
        search_pattern = f"%{search_term}%"
        params.extend([search_pattern, search_pattern, search_pattern])
    
    query += " ORDER BY p.created_at DESC"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def get_product_by_id(product_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = c.fetchone()
    conn.close()
    return product

def update_product(product_id, product_number, name, category_id, description, price, quantity, unit, supplier, min_quantity):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Get current quantity for stock movement logging
    c.execute("SELECT quantity FROM products WHERE id = ?", (product_id,))
    old_quantity = c.fetchone()[0]
    
    c.execute('''
        UPDATE products 
        SET product_number=?, name=?, category_id=?, description=?, price=?, 
            quantity=?, unit=?, supplier=?, min_quantity=?, updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    ''', (product_number, name, category_id, description, price, quantity, unit, supplier, min_quantity, product_id))
    
    # Log stock adjustment if quantity changed
    if quantity != old_quantity:
        movement_type = "INCREASE" if quantity > old_quantity else "DECREASE"
        c.execute('''
            INSERT INTO stock_movements 
            (product_id, movement_type, quantity, previous_quantity, new_quantity, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (product_id, movement_type, abs(quantity - old_quantity), old_quantity, quantity, 'Manual adjustment'))
    
    conn.commit()
    conn.close()

def delete_product(product_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()

def update_stock(product_id, quantity_change, reason):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT quantity FROM products WHERE id = ?", (product_id,))
    old_quantity = c.fetchone()[0]
    new_quantity = old_quantity + quantity_change
    
    c.execute("UPDATE products SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", 
              (new_quantity, product_id))
    
    movement_type = "INCREASE" if quantity_change > 0 else "DECREASE"
    c.execute('''
        INSERT INTO stock_movements 
        (product_id, movement_type, quantity, previous_quantity, new_quantity, reason)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (product_id, movement_type, abs(quantity_change), old_quantity, new_quantity, reason))
    
    conn.commit()
    conn.close()

def get_stock_movements(product_id=None):
    conn = sqlite3.connect(DB_FILE)
    if product_id:
        df = pd.read_sql_query("SELECT * FROM stock_movements WHERE product_id = ? ORDER BY created_at DESC", 
                               conn, params=(product_id,))
    else:
        df = pd.read_sql_query("SELECT * FROM stock_movements ORDER BY created_at DESC LIMIT 100", conn)
    conn.close()
    return df

def get_low_stock_products():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query('''
        SELECT p.*, c.name as category_name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.quantity <= p.min_quantity AND p.quantity > 0
        ORDER BY p.quantity ASC
    ''', conn)
    conn.close()
    return df

def get_out_of_stock_products():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query('''
        SELECT p.*, c.name as category_name 
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        WHERE p.quantity = 0
        ORDER BY p.name ASC
    ''', conn)
    conn.close()
    return df

def export_products_to_excel():
    products_df = get_products()
    categories_df = get_categories()
    stock_movements_df = get_stock_movements()
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        products_df.to_excel(writer, sheet_name='Products', index=False)
        categories_df.to_excel(writer, sheet_name='Categories', index=False)
        stock_movements_df.to_excel(writer, sheet_name='Stock Movements', index=False)
        
        # Add summary sheet
        summary = pd.DataFrame({
            'Metric': ['Total Products', 'Total Categories', 'Total Stock Value', 'Low Stock Items', 'Out of Stock'],
            'Value': [
                len(products_df),
                len(categories_df),
                f"${products_df['price'].sum() * products_df['quantity'].sum():,.2f}" if not products_df.empty else "$0",
                len(get_low_stock_products()),
                len(get_out_of_stock_products())
            ]
        })
        summary.to_excel(writer, sheet_name='Summary', index=False)
    
    return output.getvalue()

# ============================================================================
# Excel Upload and Import Functions
# ============================================================================

def validate_excel_columns(df, required_columns):
    """Validate if required columns exist in the DataFrame"""
    missing_columns = [col for col in required_columns if col not in df.columns]
    return missing_columns

def import_products_from_excel(df, sheet_name=None):
    """Import products from Excel DataFrame"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    success_count = 0
    error_count = 0
    errors = []
    categories_df = get_categories()
    
    for idx, row in df.iterrows():
        try:
            # Get or create category
            category_name = str(row.get('category', row.get('Category', 'Other'))).strip()
            if pd.isna(category_name) or category_name == '':
                category_name = 'Other'
            
            category_row = categories_df[categories_df['name'] == category_name]
            if category_row.empty:
                # Create new category
                add_category(category_name, f"Auto-created from Excel import")
                categories_df = get_categories()
                category_row = categories_df[categories_df['name'] == category_name]
            
            category_id = category_row.iloc[0]['id']
            
            # Get product data with proper handling of NaN values
            product_number = str(row.get('product_number', row.get('Product Number', row.get('productNumber', f"IMP_{idx}")))).strip()
            name = str(row.get('name', row.get('Name', row.get('product_name', f"Product_{idx}")))).strip()
            description = str(row.get('description', row.get('Description', ''))).strip()
            price = float(row.get('price', row.get('Price', 0)))
            quantity = int(row.get('quantity', row.get('Quantity', 0)))
            unit = str(row.get('unit', row.get('Unit', 'pcs'))).strip()
            supplier = str(row.get('supplier', row.get('Supplier', ''))).strip()
            min_quantity = int(row.get('min_quantity', row.get('Min Quantity', row.get('minQuantity', 10))))
            
            # Validate required fields
            if product_number == '' or name == '':
                errors.append(f"Row {idx + 2}: Missing product number or name")
                error_count += 1
                continue
            
            # Add product
            success, message = add_product(
                product_number, name, category_id, description, 
                price, quantity, unit, supplier, min_quantity
            )
            
            if success:
                success_count += 1
            else:
                errors.append(f"Row {idx + 2}: {message}")
                error_count += 1
                
        except Exception as e:
            errors.append(f"Row {idx + 2}: {str(e)}")
            error_count += 1
    
    conn.close()
    return success_count, error_count, errors

def import_categories_from_excel(df):
    """Import categories from Excel DataFrame"""
    success_count = 0
    error_count = 0
    errors = []
    
    for idx, row in df.iterrows():
        try:
            name = str(row.get('name', row.get('Name', ''))).strip()
            description = str(row.get('description', row.get('Description', ''))).strip()
            
            if name:
                success, message = add_category(name, description)
                if success:
                    success_count += 1
                else:
                    errors.append(f"Row {idx + 2}: {message}")
                    error_count += 1
        except Exception as e:
            errors.append(f"Row {idx + 2}: {str(e)}")
            error_count += 1
    
    return success_count, error_count, errors

def preview_excel_file(uploaded_file):
    """Preview Excel file with multiple sheets"""
    try:
        excel_file = pd.ExcelFile(uploaded_file)
        sheet_names = excel_file.sheet_names
        
        st.info(f"📊 Excel file contains {len(sheet_names)} sheet(s): {', '.join(sheet_names)}")
        
        selected_sheet = st.selectbox("Select sheet to preview", sheet_names)
        df = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
        
        st.subheader(f"Preview of sheet: {selected_sheet}")
        st.dataframe(df.head(10))
        
        st.subheader("Data Information")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Rows", len(df))
        with col2:
            st.metric("Columns", len(df.columns))
        with col3:
            st.metric("Memory Usage", f"{df.memory_usage(deep=True).sum() / 1024:.2f} KB")
        
        st.subheader("Column Information")
        col_info = pd.DataFrame({
            'Column': df.columns,
            'Type': df.dtypes.values,
            'Non-Null Count': df.count().values,
            'Null Count': df.isnull().sum().values
        })
        st.dataframe(col_info)
        
        return df, selected_sheet
    except Exception as e:
        st.error(f"Error reading Excel file: {str(e)}")
        return None, None

# ============================================================================
# UI Components
# ============================================================================

st.set_page_config(
    page_title="Product Management System",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
    }
    .warning-card {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
    .success-card {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
    .info-card {
        background-color: #d1ecf1;
        border-left: 4px solid #17a2b8;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.markdown("""
    <div style="text-align: center;">
        <h1>📦</h1>
        <h3>Product Management</h3>
    </div>
""", unsafe_allow_html=True)
st.sidebar.markdown("---")

menu = st.sidebar.selectbox(
    "Main Menu",
    ["Dashboard", "Products", "Categories", "Stock Management", "Analytics", "Export/Import", "Excel Upload"]
)

# ============================================================================
# Dashboard
# ============================================================================

if menu == "Dashboard":
    st.markdown('<div class="main-header"><h1>📊 Dashboard</h1><p>Product Management Overview</p></div>', unsafe_allow_html=True)
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    products_df = get_products()
    total_products = len(products_df)
    total_categories = len(get_categories())
    total_stock_value = (products_df['price'] * products_df['quantity']).sum() if not products_df.empty else 0
    low_stock = len(get_low_stock_products())
    
    with col1:
        st.metric("Total Products", total_products)
    with col2:
        st.metric("Total Categories", total_categories)
    with col3:
        st.metric("Total Stock Value", f"${total_stock_value:,.2f}")
    with col4:
        st.metric("Low Stock Items", low_stock, delta="Need attention" if low_stock > 0 else "OK")
    
    # Alerts
    out_of_stock = get_out_of_stock_products()
    if not out_of_stock.empty:
        st.markdown('<div class="warning-card">⚠️ <strong>Out of Stock Items</strong></div>', unsafe_allow_html=True)
        st.dataframe(out_of_stock[['product_number', 'name', 'category_name', 'supplier']], use_container_width=True)
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Products by Category")
        if not products_df.empty:
            category_counts = products_df['category_name'].value_counts()
            fig = px.pie(values=category_counts.values, names=category_counts.index, title="Distribution")
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Stock Levels")
        if not products_df.empty:
            top_products = products_df.nlargest(10, 'quantity')[['name', 'quantity']]
            fig = px.bar(top_products, x='name', y='quantity', title="Top 10 Products by Quantity")
            st.plotly_chart(fig, use_container_width=True)
    
    # Recent products
    st.subheader("Recent Products")
    recent_products = products_df.head(10) if not products_df.empty else pd.DataFrame()
    st.dataframe(recent_products[['product_number', 'name', 'category_name', 'price', 'quantity']], use_container_width=True)

# ============================================================================
# Products CRUD
# ============================================================================

elif menu == "Products":
    st.markdown('<div class="main-header"><h1>📝 Products Management</h1><p>Create, Read, Update, Delete Products</p></div>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["Product List", "Add Product", "Edit/Delete Product"])
    
    with tab1:
        st.subheader("All Products")
        
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            categories_df = get_categories()
            category_options = ['All'] + categories_df['id'].tolist()
            category_names = ['All'] + categories_df['name'].tolist()
            selected_category = st.selectbox("Filter by Category", category_options, format_func=lambda x: category_names[category_options.index(x)])
        
        with col2:
            search_term = st.text_input("Search Products", placeholder="Search by name, number or description...")
        
        filter_category = None if selected_category == 'All' else selected_category
        products = get_products(filter_category, search_term)
        
        if not products.empty:
            # Display products with formatting
            display_df = products[['product_number', 'name', 'category_name', 'price', 'quantity', 'unit', 'supplier']].copy()
            display_df['price'] = display_df['price'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(display_df, use_container_width=True)
            
            # Download button
            csv = products.to_csv(index=False)
            st.download_button("📥 Download as CSV", csv, "products.csv", "text/csv")
        else:
            st.info("No products found")
    
    with tab2:
        st.subheader("Add New Product")
        
        with st.form("add_product_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                product_number = st.text_input("Product Number *", help="Unique identifier for the product")
                name = st.text_input("Product Name *")
                categories_df = get_categories()
                category_id = st.selectbox("Category", categories_df['id'].tolist(), format_func=lambda x: categories_df[categories_df['id']==x]['name'].iloc[0])
                price = st.number_input("Price", min_value=0.0, step=0.01)
                quantity = st.number_input("Quantity", min_value=0, step=1)
            
            with col2:
                unit = st.selectbox("Unit", ["pcs", "kg", "liters", "meters", "boxes", "packs"])
                supplier = st.text_input("Supplier")
                min_quantity = st.number_input("Minimum Quantity Alert", min_value=0, step=1, value=10)
                description = st.text_area("Description", height=100)
            
            submitted = st.form_submit_button("Add Product")
            if submitted:
                if not product_number or not name:
                    st.error("Product Number and Name are required!")
                else:
                    success, message = add_product(product_number, name, category_id, description, price, quantity, unit, supplier, min_quantity)
                    if success:
                        st.success(message)
                        st.balloons()
                    else:
                        st.error(message)
    
    with tab3:
        st.subheader("Edit or Delete Product")
        
        products = get_products()
        if not products.empty:
            product_options = products['id'].tolist()
            selected_product = st.selectbox("Select Product", product_options, format_func=lambda x: f"{x} - {products[products['id']==x]['name'].iloc[0]}")
            
            if selected_product:
                product = products[products['id'] == selected_product].iloc[0]
                
                with st.form("edit_product_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        edit_product_number = st.text_input("Product Number", product['product_number'])
                        edit_name = st.text_input("Product Name", product['name'])
                        categories_df = get_categories()
                        current_category_id = product['category_id'] if pd.notna(product['category_id']) else None
                        if current_category_id and current_category_id in categories_df['id'].tolist():
                            default_index = categories_df['id'].tolist().index(current_category_id)
                        else:
                            default_index = 0
                        edit_category_id = st.selectbox("Category", categories_df['id'].tolist(), 
                                                        index=default_index,
                                                        format_func=lambda x: categories_df[categories_df['id']==x]['name'].iloc[0])
                        edit_price = st.number_input("Price", value=float(product['price']), step=0.01)
                        edit_quantity = st.number_input("Quantity", value=int(product['quantity']), step=1)
                    
                    with col2:
                        unit_options = ["pcs", "kg", "liters", "meters", "boxes", "packs"]
                        current_unit = product['unit'] if pd.notna(product['unit']) else "pcs"
                        edit_unit = st.selectbox("Unit", unit_options, 
                                                index=unit_options.index(current_unit) if current_unit in unit_options else 0)
                        edit_supplier = st.text_input("Supplier", product['supplier'] if pd.notna(product['supplier']) else "")
                        edit_min_quantity = st.number_input("Minimum Quantity Alert", value=int(product['min_quantity']), step=1)
                        edit_description = st.text_area("Description", product['description'] if pd.notna(product['description']) else "", height=100)
                    
                    update_submitted = st.form_submit_button("Update Product")
                    if update_submitted:
                        update_product(selected_product, edit_product_number, edit_name, edit_category_id, 
                                     edit_description, edit_price, edit_quantity, edit_unit, edit_supplier, edit_min_quantity)
                        st.success("Product updated successfully!")
                        st.rerun()
                
                if st.button("Delete Product", type="secondary"):
                    delete_product(selected_product)
                    st.warning("Product deleted!")
                    st.rerun()
        else:
            st.info("No products available")

# ============================================================================
# Categories Management
# ============================================================================

elif menu == "Categories":
    st.markdown('<div class="main-header"><h1>🏷️ Categories Management</h1><p>Manage Product Categories</p></div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Add New Category")
        with st.form("add_category_form"):
            cat_name = st.text_input("Category Name")
            cat_description = st.text_area("Description")
            submitted = st.form_submit_button("Add Category")
            if submitted and cat_name:
                success, message = add_category(cat_name, cat_description)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    
    with col2:
        st.subheader("Existing Categories")
        categories = get_categories()
        if not categories.empty:
            for _, cat in categories.iterrows():
                with st.expander(f"📁 {cat['name']}"):
                    st.write(f"**Description:** {cat['description']}")
                    st.write(f"**Created:** {cat['created_at']}")
                    
                    # Check if category has products
                    products_in_cat = get_products(filter_category=cat['id'])
                    st.write(f"**Products:** {len(products_in_cat)}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"Edit {cat['name']}", key=f"edit_{cat['id']}"):
                            # Edit category modal
                            with st.form(f"edit_category_{cat['id']}"):
                                new_name = st.text_input("Name", cat['name'])
                                new_desc = st.text_area("Description", cat['description'])
                                if st.form_submit_button("Update"):
                                    update_category(cat['id'], new_name, new_desc)
                                    st.success("Category updated!")
                                    st.rerun()
                    
                    with col2:
                        if len(products_in_cat) == 0:
                            if st.button(f"Delete {cat['name']}", key=f"delete_{cat['id']}"):
                                delete_category(cat['id'])
                                st.warning("Category deleted!")
                                st.rerun()
                        else:
                            st.info(f"Cannot delete - contains {len(products_in_cat)} products")

# ============================================================================
# Stock Management
# ============================================================================

elif menu == "Stock Management":
    st.markdown('<div class="main-header"><h1>📊 Stock Management</h1><p>Track and Update Inventory</p></div>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["Stock Adjustment", "Stock Movements", "Alerts"])
    
    with tab1:
        st.subheader("Adjust Stock Levels")
        
        products = get_products()
        if not products.empty:
            product_options = products['id'].tolist()
            selected_product = st.selectbox("Select Product", product_options, 
                                           format_func=lambda x: f"{products[products['id']==x]['product_number'].iloc[0]} - {products[products['id']==x]['name'].iloc[0]}")
            
            if selected_product:
                product = products[products['id'] == selected_product].iloc[0]
                current_quantity = product['quantity']
                
                st.write(f"**Current Quantity:** {current_quantity} {product['unit']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    adjustment = st.number_input("Quantity Adjustment", value=0, step=1, 
                                                help="Positive for increase, negative for decrease")
                with col2:
                    reason = st.text_input("Reason for Adjustment", placeholder="e.g., Stock received, damaged, sold, etc.")
                
                if st.button("Apply Adjustment"):
                    if adjustment != 0 and reason:
                        update_stock(selected_product, adjustment, reason)
                        st.success(f"Stock updated! New quantity: {current_quantity + adjustment} {product['unit']}")
                        st.rerun()
                    else:
                        st.error("Please provide both adjustment value and reason")
        else:
            st.info("No products available")
    
    with tab2:
        st.subheader("Stock Movement History")
        
        product_filter = st.selectbox("Filter by Product", ["All"] + products['id'].tolist() if not products.empty else ["All"],
                                     format_func=lambda x: "All" if x == "All" else f"{products[products['id']==x]['product_number'].iloc[0]} - {products[products['id']==x]['name'].iloc[0]}")
        
        if product_filter == "All":
            movements = get_stock_movements()
        else:
            movements = get_stock_movements(product_filter)
        
        if not movements.empty:
            st.dataframe(movements, use_container_width=True)
            
            # Visualize movements
            if len(movements) > 0:
                fig = px.line(movements, x='created_at', y='new_quantity', title="Stock Level Over Time")
                st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.subheader("Stock Alerts")
        
        low_stock = get_low_stock_products()
        out_of_stock = get_out_of_stock_products()
        
        if not low_stock.empty:
            st.warning(f"⚠️ {len(low_stock)} products are below minimum quantity level")
            st.dataframe(low_stock[['product_number', 'name', 'category_name', 'quantity', 'min_quantity', 'supplier']], use_container_width=True)
        
        if not out_of_stock.empty:
            st.error(f"❌ {len(out_of_stock)} products are out of stock")
            st.dataframe(out_of_stock[['product_number', 'name', 'category_name', 'supplier']], use_container_width=True)
        
        if low_stock.empty and out_of_stock.empty:
            st.success("✅ All products have adequate stock levels!")

# ============================================================================
# Analytics
# ============================================================================

elif menu == "Analytics":
    st.markdown('<div class="main-header"><h1>📈 Analytics Dashboard</h1><p>Product and Sales Analysis</p></div>', unsafe_allow_html=True)
    
    products = get_products()
    
    if not products.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Stock Value by Category")
            category_value = products.groupby('category_name').apply(lambda x: (x['price'] * x['quantity']).sum()).reset_index()
            category_value.columns = ['Category', 'Total Value']
            fig = px.pie(category_value, values='Total Value', names='Category', title="Inventory Value Distribution")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Top 10 Products by Value")
            products['total_value'] = products['price'] * products['quantity']
            top_value = products.nlargest(10, 'total_value')[['name', 'total_value']]
            fig = px.bar(top_value, x='name', y='total_value', title="Highest Value Products")
            st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("Stock Distribution")
        fig = px.histogram(products, x='quantity', nbins=20, title="Stock Quantity Distribution")
        st.plotly_chart(fig, use_container_width=True)
        
        st.subheader("Price vs Quantity Analysis")
        fig = px.scatter(products, x='price', y='quantity', color='category_name', 
                        size='total_value', hover_data=['name'], title="Price vs Quantity")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data available for analysis")

# ============================================================================
# Export/Import
# ============================================================================

elif menu == "Export/Import":
    st.markdown('<div class="main-header"><h1>📤 Export / Import</h1><p>Data Backup and Migration</p></div>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Export Data", "Import Data"])
    
    with tab1:
        st.subheader("Export Data to Excel")
        
        export_format = st.selectbox("Export Format", ["Excel (.xlsx)", "CSV", "JSON"])
        
        if st.button("Generate Export File"):
            if export_format == "Excel (.xlsx)":
                excel_data = export_products_to_excel()
                st.download_button(
                    label="📥 Download Excel File",
                    data=excel_data,
                    file_name=f"products_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            elif export_format == "CSV":
                products = get_products()
                csv = products.to_csv(index=False)
                st.download_button(
                    label="📥 Download CSV File",
                    data=csv,
                    file_name=f"products_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            elif export_format == "JSON":
                products = get_products()
                json_data = products.to_json(orient='records', date_format='iso')
                st.download_button(
                    label="📥 Download JSON File",
                    data=json_data,
                    file_name=f"products_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
    
    with tab2:
        st.subheader("Import Data from CSV")
        st.info("CSV file should contain columns: product_number, name, category, description, price, quantity, unit, supplier, min_quantity")
        
        uploaded_file = st.file_uploader("Choose CSV file", type=['csv'])
        
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.write("Preview of data to import:")
                st.dataframe(df.head())
                
                if st.button("Import Data"):
                    categories_df = get_categories()
                    success_count = 0
                    error_count = 0
                    
                    for _, row in df.iterrows():
                        try:
                            # Find or create category
                            category_name = row.get('category', 'Other')
                            category_row = categories_df[categories_df['name'] == category_name]
                            if category_row.empty:
                                add_category(category_name, f"Auto-created category for {category_name}")
                                categories_df = get_categories()
                                category_row = categories_df[categories_df['name'] == category_name]
                            
                            category_id = category_row.iloc[0]['id']
                            
                            add_product(
                                str(row['product_number']),
                                row['name'],
                                category_id,
                                row.get('description', ''),
                                float(row.get('price', 0)),
                                int(row.get('quantity', 0)),
                                row.get('unit', 'pcs'),
                                row.get('supplier', ''),
                                int(row.get('min_quantity', 10))
                            )
                            success_count += 1
                        except Exception as e:
                            error_count += 1
                            st.error(f"Error importing {row.get('product_number', 'Unknown')}: {str(e)}")
                    
                    st.success(f"Import completed! {success_count} products imported, {error_count} errors")
                    st.rerun()
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")

# ============================================================================
# Excel Upload (NEW!)
# ============================================================================

elif menu == "Excel Upload":
    st.markdown('<div class="main-header"><h1>📂 Excel Upload & Import</h1><p>Upload Excel files to import products and categories</p></div>', unsafe_allow_html=True)
    
    st.markdown('<div class="info-card">ℹ️ <strong>Instructions:</strong><br>Upload Excel files with product or category data. The system will automatically detect the structure and import the data.</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📝 Template Format")
        st.markdown("""
        **Product Import Format:**
        - product_number (required)
        - name (required)
        - category (optional, default: Other)
        - description (optional)
        - price (optional, default: 0)
        - quantity (optional, default: 0)
        - unit (optional, default: pcs)
        - supplier (optional)
        - min_quantity (optional, default: 10)
        
        **Category Import Format:**
        - name (required)
        - description (optional)
        """)
        
        # Download template
        template_df = pd.DataFrame({
            'product_number': ['PRD001', 'PRD002'],
            'name': ['Sample Product 1', 'Sample Product 2'],
            'category': ['Electronics', 'Clothing'],
            'description': ['Description here', 'Another description'],
            'price': [99.99, 49.99],
            'quantity': [100, 50],
            'unit': ['pcs', 'pcs'],
            'supplier': ['Supplier A', 'Supplier B'],
            'min_quantity': [10, 5]
        })
        
        template_buffer = io.BytesIO()
        with pd.ExcelWriter(template_buffer, engine='openpyxl') as writer:
            template_df.to_excel(writer, sheet_name='Products', index=False)
            categories_template = pd.DataFrame({
                'name': ['Electronics', 'Clothing'],
                'description': ['Electronic devices', 'Apparel items']
            })
            categories_template.to_excel(writer, sheet_name='Categories', index=False)
        
        st.download_button(
            label="📥 Download Excel Template",
            data=template_buffer.getvalue(),
            file_name="product_import_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    with col2:
        st.markdown("### 📤 Upload Excel File")
        uploaded_file = st.file_uploader("Choose an Excel file", type=['xlsx', 'xls'])
        
        if uploaded_file:
            # Preview file
            df_preview, sheet_name = preview_excel_file(uploaded_file)
            
            if df_preview is not None:
                st.markdown("### 🚀 Import Options")
                
                import_type = st.radio(
                    "Select import type",
                    ["Import Products", "Import Categories", "Auto-detect"]
                )
                
                if st.button("Start Import", type="primary"):
                    with st.spinner("Importing data..."):
                        if import_type == "Import Products" or (import_type == "Auto-detect" and 'product_number' in df_preview.columns):
                            success, errors, error_list = import_products_from_excel(df_preview, sheet_name)
                            
                            if success > 0:
                                st.markdown(f'<div class="success-card">✅ Successfully imported {success} products!</div>', unsafe_allow_html=True)
                            if errors > 0:
                                st.markdown(f'<div class="warning-card">⚠️ {errors} errors occurred during import</div>', unsafe_allow_html=True)
                                with st.expander("View errors"):
                                    for error in error_list[:20]:  # Show first 20 errors
                                        st.error(error)
                        
                        elif import_type == "Import Categories" or (import_type == "Auto-detect" and 'name' in df_preview.columns and 'product_number' not in df_preview.columns):
                            success, errors, error_list = import_categories_from_excel(df_preview)
                            
                            if success > 0:
                                st.markdown(f'<div class="success-card">✅ Successfully imported {success} categories!</div>', unsafe_allow_html=True)
                            if errors > 0:
                                st.markdown(f'<div class="warning-card">⚠️ {errors} errors occurred during import</div>', unsafe_allow_html=True)
                                with st.expander("View errors"):
                                    for error in error_list[:20]:
                                        st.error(error)
                        else:
                            st.error("Could not detect data type. Please ensure your file has the correct columns.")
                        
                        st.rerun()

# ============================================================================
# Footer
# ============================================================================

st.sidebar.markdown("---")
st.sidebar.info(
    """
    **Version:** 2.0  
    **Features:**  
    • Product CRUD  
    • Category Management  
    • Stock Tracking  
    • Excel Import/Export  
    • Analytics Dashboard  
    """
)