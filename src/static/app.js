// Front-end Dashboard Logic - Nexus OMS

let stockChartInstance = null;
let activeTab = 'dashboard';
let currentOrdersFilter = 'ALL';

// Initialize SPA
document.addEventListener("DOMContentLoaded", () => {
    setupTabNavigation();
    loadDashboardData();
    preloadFormSelects();
});

// ==========================================
// SPA Tab Navigation Controls
// ==========================================
function setupTabNavigation() {
    const navItems = document.querySelectorAll(".nav-item");
    navItems.forEach(item => {
        item.addEventListener("click", () => {
            const targetTab = item.getAttribute("data-tab");
            switchTab(targetTab);
        });
    });
}

function switchTab(tabName) {
    activeTab = tabName;
    
    // Toggle active classes in sidebar
    document.querySelectorAll(".nav-item").forEach(item => {
        if (item.getAttribute("data-tab") === tabName) {
            item.classList.add("active");
        } else {
            item.classList.remove("active");
        }
    });

    // Toggle active panels
    document.querySelectorAll(".tab-panel").forEach(panel => {
        panel.classList.remove("active");
    });
    document.getElementById(`${tabName}-tab`).classList.add("active");

    // Dynamic header titles
    const title = document.getElementById("page-title");
    const subtitle = document.getElementById("page-subtitle");

    switch(tabName) {
        case 'dashboard':
            title.textContent = "Operations Dashboard";
            subtitle.textContent = "Real-time warehouse metrics and controls";
            loadDashboardData();
            break;
        case 'products':
            title.textContent = "Product Catalog";
            subtitle.textContent = "View, add, edit, and adjust inventory products";
            loadProducts();
            break;
        case 'orders':
            title.textContent = "Order Ledger";
            subtitle.textContent = "Track, fulfill, or cancel customer orders";
            loadOrders();
            break;
        case 'customers':
            title.textContent = "Customer Directory";
            subtitle.textContent = "Client listing and contact ledger";
            loadCustomers();
            break;
        case 'suppliers':
            title.textContent = "Supplier Directories";
            subtitle.textContent = "Manage wholesale supplier records";
            loadSuppliers();
            break;
        case 'transactions':
            title.textContent = "Inventory Audit Logs";
            subtitle.textContent = "Complete stock transactions and adjustments log";
            loadTransactions();
            break;
    }
}

// ==========================================
// Dashboard Analytics & Charts
// ==========================================
async function loadDashboardData() {
    try {
        const res = await fetch("/api/dashboard");
        if (!res.ok) throw new Error("Could not fetch dashboard metrics");
        const data = await res.json();

        // Update KPIs
        document.getElementById("kpi-revenue").textContent = `$${data.total_revenue.toFixed(2)}`;
        document.getElementById("kpi-orders").textContent = data.active_orders_count;
        document.getElementById("kpi-valuation").textContent = `$${data.inventory_value.toFixed(2)}`;
        document.getElementById("kpi-lowstock").textContent = data.low_stock_count;

        // Add warning class if low stock exists
        const lowStockCard = document.getElementById("kpi-lowstock").closest('.kpi-card');
        if (data.low_stock_count > 0) {
            lowStockCard.classList.add("alert");
        } else {
            lowStockCard.classList.remove("alert");
        }

        // Render Recent Logs Table
        const logTable = document.getElementById("recent-logs-table");
        logTable.innerHTML = "";
        
        if (data.recent_transactions.length === 0) {
            logTable.innerHTML = "<tr><td colspan='5' class='loading-cell'>No activity recorded yet</td></tr>";
        } else {
            data.recent_transactions.slice(0, 5).forEach(tx => {
                const tr = document.createElement("tr");
                const directionBadge = tx.type === 'IN' 
                    ? `<span class="badge badge-in"><i class="fa-solid fa-arrow-turn-down"></i> IN</span>`
                    : `<span class="badge badge-out"><i class="fa-solid fa-arrow-turn-up"></i> OUT</span>`;
                
                tr.innerHTML = `
                    <td><strong>${tx.product_name}</strong><br><small class="text-muted">${tx.sku}</small></td>
                    <td>${directionBadge}</td>
                    <td>${tx.quantity}</td>
                    <td>${tx.reason}</td>
                    <td class="text-muted">${tx.created_at.split(' ')[1]}</td>
                `;
                logTable.appendChild(tr);
            });
        }

        // Load Chart
        loadChartData();

    } catch (err) {
        showToast(err.message, "error");
    }
}

async function loadChartData() {
    try {
        const res = await fetch("/api/products");
        if (!res.ok) throw new Error("Could not fetch chart data");
        const products = await res.json();

        // Prepare chart context
        const ctx = document.getElementById("stockChart").getContext("2d");
        
        const labels = products.map(p => p.sku);
        const stockValues = products.map(p => p.stock_quantity);
        const prices = products.map(p => p.price);

        // Map colors (red glow for low stock <= 5)
        const backgroundColors = products.map(p => 
            p.stock_quantity <= 5 ? 'rgba(244, 63, 94, 0.6)' : 'rgba(99, 102, 241, 0.5)'
        );
        const borderColors = products.map(p => 
            p.stock_quantity <= 5 ? 'rgb(244, 63, 94)' : 'rgb(99, 102, 241)'
        );

        if (stockChartInstance) {
            stockChartInstance.destroy();
        }

        stockChartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'In-Stock Quantity',
                        data: stockValues,
                        backgroundColor: backgroundColors,
                        borderColor: borderColors,
                        borderWidth: 1.5,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Unit Price ($)',
                        data: prices,
                        type: 'line',
                        borderColor: '#22d3ee',
                        backgroundColor: 'rgba(6, 182, 212, 0.1)',
                        borderWidth: 2,
                        pointRadius: 4,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8', font: { family: 'Outfit' } }
                    },
                    y: {
                        position: 'left',
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8', font: { family: 'Outfit' } },
                        title: { display: true, text: 'Quantity', color: '#94a3b8' }
                    },
                    y1: {
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        ticks: { color: '#22d3ee', font: { family: 'Outfit' } },
                        title: { display: true, text: 'Price ($)', color: '#22d3ee' }
                    }
                },
                plugins: {
                    legend: {
                        labels: { color: '#f8fafc', font: { family: 'Outfit' } }
                    }
                }
            }
        });

    } catch (err) {
        console.error(err);
    }
}

// ==========================================
// Products Catalog Loading & CRUD
// ==========================================
async function loadProducts() {
    const searchVal = document.getElementById("product-search").value;
    const lowStockOnly = document.getElementById("product-filter-low").checked;
    
    let url = `/api/products?search=${encodeURIComponent(searchVal)}`;
    if (lowStockOnly) {
        url += `&low_stock=true`;
    }

    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error("Could not fetch products");
        const products = await res.json();

        const tableBody = document.getElementById("products-table");
        tableBody.innerHTML = "";

        if (products.length === 0) {
            tableBody.innerHTML = "<tr><td colspan='7' class='loading-cell'>No products matching filters found</td></tr>";
            return;
        }

        products.forEach(p => {
            let statusText = "In Stock";
            let statusClass = "status-instock";
            if (p.stock_quantity === 0) {
                statusText = "Out of Stock";
                statusClass = "status-outofstock";
            } else if (p.stock_quantity <= 5) {
                statusText = "Low Stock";
                statusClass = "status-lowstock";
            }

            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><span class="badge badge-shipped">${p.sku}</span></td>
                <td><strong>${p.name}</strong><br><small class="text-muted">${p.description || 'No description'}</small></td>
                <td>${p.supplier_name}</td>
                <td>$${p.price.toFixed(2)}</td>
                <td>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <strong>${p.stock_quantity}</strong>
                        <button class="btn btn-icon btn-small" onclick="promptStockAdjust(${p.id}, '${p.name}', ${p.stock_quantity})">
                            <i class="fa-solid fa-arrow-trend-up"></i>
                        </button>
                    </div>
                </td>
                <td>
                    <span class="status-pill ${statusClass}">
                        <span class="status-dot"></span> ${statusText}
                    </span>
                </td>
                <td class="actions-header">
                    <div class="action-buttons">
                        <button class="btn-icon edit" title="Edit Product Info" onclick="editProductPrompt(${JSON.stringify(p).replace(/"/g, '&quot;')})">
                            <i class="fa-solid fa-pen-to-square"></i>
                        </button>
                        <button class="btn-icon delete" title="Delete Product" onclick="deleteProduct(${p.id})">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </div>
                </td>
            `;
            tableBody.appendChild(tr);
        });

    } catch (err) {
        showToast(err.message, "error");
    }
}

async function submitProduct(event) {
    event.preventDefault();
    const pid = document.getElementById("product-id-field").value;
    const sku = document.getElementById("product-sku").value;
    const name = document.getElementById("product-name").value;
    const price = parseFloat(document.getElementById("product-price").value);
    const stock = parseInt(document.getElementById("product-stock").value);
    const supplier_id = parseInt(document.getElementById("product-supplier").value);
    const description = document.getElementById("product-desc").value;

    const isEdit = !!pid;
    const url = isEdit ? `/api/products/${pid}` : `/api/products`;
    const method = isEdit ? 'PUT' : 'POST';

    const payload = isEdit 
        ? { name, price, supplier_id, description } 
        : { sku, name, price, stock_quantity: stock, supplier_id, description };

    try {
        const res = await fetch(url, {
            method: method,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Validation or database error occurred.");
        }

        showToast(isEdit ? "Product updated successfully!" : "Product added to database!", "success");
        closeModal('product-modal');
        loadProducts();
        preloadFormSelects(); // refresh options list
    } catch (err) {
        showToast(err.message, "error");
    }
}

function editProductPrompt(p) {
    document.getElementById("product-modal-title").textContent = "Edit Product Info";
    document.getElementById("product-id-field").value = p.id;
    document.getElementById("product-sku").value = p.sku;
    document.getElementById("product-sku").disabled = true; // SKU cannot be edited
    document.getElementById("product-name").value = p.name;
    document.getElementById("product-price").value = p.price;
    document.getElementById("product-supplier").value = p.supplier_id;
    document.getElementById("product-desc").value = p.description || "";
    
    // Hide stock field for basic edits (stock is managed through specific adjustments log)
    document.getElementById("product-stock-group").style.display = "none";
    document.getElementById("product-stock").required = false;

    openModal('product-modal');
}

function promptStockAdjust(id, name, currentStock) {
    const adjustAmountStr = prompt(`Adjust Stock for "${name}" (Current Stock: ${currentStock}):\n\nEnter positive number to restock, or negative to deduct:`);
    if (adjustAmountStr === null) return; // cancelled

    const change = parseInt(adjustAmountStr);
    if (isNaN(change) || change === 0) {
        alert("Please enter a valid non-zero integer.");
        return;
    }

    const reason = prompt("Enter reason code for adjustment (e.g. Monthly Restock, Damage):", "Manual Adjustment") || "Manual Adjustment";

    fetch(`/api/products/${id}`, {
        method: 'PUT',
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stock_quantity: currentStock + change }) // backend will calculate diff and log
    })
    .then(async res => {
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Error adjusting stock.");
        showToast("Stock level adjusted successfully", "success");
        loadProducts();
    })
    .catch(err => {
        showToast(err.message, "error");
    });
}

async function deleteProduct(id) {
    if (!confirm("Are you sure you want to permanently delete this product? This will fail if it has history orders.")) return;
    try {
        const res = await fetch(`/api/products/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to delete product.");
        showToast("Product deleted successfully", "success");
        loadProducts();
    } catch (err) {
        showToast(err.message, "error");
    }
}

// ==========================================
// Orders Ledger Controls & Status Updates
// ==========================================
async function loadOrders() {
    let url = `/api/orders`;
    if (currentOrdersFilter !== 'ALL') {
        url += `?status=${currentOrdersFilter}`;
    }

    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error("Could not fetch orders ledger");
        const orders = await res.json();

        const tableBody = document.getElementById("orders-table");
        tableBody.innerHTML = "";

        if (orders.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="7" class="loading-cell">No ${currentOrdersFilter.toLowerCase()} orders found</td></tr>`;
            return;
        }

        orders.forEach(o => {
            let badgeClass = "badge-pending";
            if (o.status === "SHIPPED") badgeClass = "badge-shipped";
            else if (o.status === "DELIVERED") badgeClass = "badge-delivered";
            else if (o.status === "CANCELLED") badgeClass = "badge-cancelled";

            // Compile items summary line
            const itemsSummary = o.items.map(item => `${item.quantity}x ${item.product_name}`).join(", ");

            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><strong>#${o.id}</strong></td>
                <td><strong>${o.customer_name}</strong><br><small class="text-muted">${o.customer_email}</small></td>
                <td style="max-width: 250px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;" title="${itemsSummary}">${itemsSummary}</td>
                <td>${o.order_date}</td>
                <td><strong>$${o.total_amount.toFixed(2)}</strong></td>
                <td><span class="badge ${badgeClass}">${o.status}</span></td>
                <td class="actions-header">
                    <select class="status-select" onchange="updateOrderStatus(${o.id}, this.value)">
                        <option value="PENDING" ${o.status === 'PENDING' ? 'selected' : ''}>PENDING</option>
                        <option value="SHIPPED" ${o.status === 'SHIPPED' ? 'selected' : ''}>SHIPPED</option>
                        <option value="DELIVERED" ${o.status === 'DELIVERED' ? 'selected' : ''}>DELIVERED</option>
                        <option value="CANCELLED" ${o.status === 'CANCELLED' ? 'selected' : ''}>CANCELLED</option>
                    </select>
                </td>
            `;
            tableBody.appendChild(tr);
        });

    } catch (err) {
        showToast(err.message, "error");
    }
}

function filterOrders(btn) {
    document.querySelectorAll(".btn-tab").forEach(tab => tab.classList.remove("active"));
    btn.classList.add("active");
    currentOrdersFilter = btn.getAttribute("data-status-filter");
    loadOrders();
}

async function updateOrderStatus(orderId, newStatus) {
    try {
        const res = await fetch(`/api/orders/${orderId}/status`, {
            method: 'PUT',
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: newStatus })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to update order status.");
        
        showToast(`Order #${orderId} status set to ${newStatus}`, "success");
        loadOrders();
    } catch (err) {
        showToast(err.message, "error");
        loadOrders(); // restore selector state on error
    }
}

// Order dynamic form item row builder
let orderItemCounter = 0;
async function addOrderItemField() {
    // Get product catalog options
    const res = await fetch("/api/products");
    const products = await res.json();
    
    if (products.length === 0) {
        alert("Please add products to the catalog first.");
        return;
    }

    const container = document.getElementById("order-items-container");
    const rowId = `order-row-${orderItemCounter++}`;
    
    const row = document.createElement("div");
    row.className = "order-item-row";
    row.id = rowId;

    let optionsHtml = products.map(p => `
        <option value="${p.id}">${p.sku} - ${p.name} ($${p.price.toFixed(2)} | Stock: ${p.stock_quantity})</option>
    `).join("");

    row.innerHTML = `
        <select class="order-product-select" required>
            <option value="">Select a product...</option>
            ${optionsHtml}
        </select>
        <input type="number" class="order-qty-input" min="1" placeholder="Qty" value="1" required>
        <button type="button" class="btn btn-icon delete btn-small" onclick="removeOrderItemField('${rowId}')">
            <i class="fa-solid fa-trash"></i>
        </button>
    `;
    
    container.appendChild(row);
}

function removeOrderItemField(rowId) {
    const el = document.getElementById(rowId);
    if (el) el.remove();
}

async function submitOrder(event) {
    event.preventDefault();
    const customer_id = parseInt(document.getElementById("order-customer").value);
    
    const itemRows = document.querySelectorAll(".order-item-row");
    const items = [];
    
    itemRows.forEach(row => {
        const product_id = parseInt(row.querySelector(".order-product-select").value);
        const quantity = parseInt(row.querySelector(".order-qty-input").value);
        if (product_id && quantity > 0) {
            items.push({ product_id, quantity });
        }
    });

    if (items.length === 0) {
        alert("Please select at least one item to place order.");
        return;
    }

    try {
        const res = await fetch("/api/orders", {
            method: 'POST',
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ customer_id, items })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Unable to fulfill order.");

        showToast(`Order successfully completed! Total: $${data.total.toFixed(2)}`, "success");
        closeModal('order-modal');
        if (activeTab === 'orders') loadOrders();
        else if (activeTab === 'dashboard') loadDashboardData();
    } catch (err) {
        showToast(err.message, "error");
    }
}

// ==========================================
// Customers & Suppliers Ledger Loading
// ==========================================
async function loadCustomers() {
    try {
        const res = await fetch("/api/customers");
        const customers = await res.json();
        const tableBody = document.getElementById("customers-table");
        tableBody.innerHTML = "";

        if (customers.length === 0) {
            tableBody.innerHTML = "<tr><td colspan='5' class='loading-cell'>No customers registered</td></tr>";
            return;
        }

        customers.forEach(c => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><span class="text-muted">#${c.id}</span></td>
                <td><strong>${c.name}</strong></td>
                <td>${c.email}</td>
                <td>${c.phone || '<span class="text-muted">N/A</span>'}</td>
                <td>${c.address || '<span class="text-muted">No address registered</span>'}</td>
            `;
            tableBody.appendChild(tr);
        });
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function submitCustomer(event) {
    event.preventDefault();
    const name = document.getElementById("customer-name").value;
    const email = document.getElementById("customer-email").value;
    const phone = document.getElementById("customer-phone").value;
    const address = document.getElementById("customer-address").value;

    try {
        const res = await fetch("/api/customers", {
            method: 'POST',
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, phone, address })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to register customer.");
        showToast("Customer added successfully", "success");
        closeModal('customer-modal');
        loadCustomers();
        preloadFormSelects();
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function loadSuppliers() {
    try {
        const res = await fetch("/api/suppliers");
        const suppliers = await res.json();
        const tableBody = document.getElementById("suppliers-table");
        tableBody.innerHTML = "";

        if (suppliers.length === 0) {
            tableBody.innerHTML = "<tr><td colspan='4' class='loading-cell'>No suppliers registered</td></tr>";
            return;
        }

        suppliers.forEach(s => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><span class="text-muted">#${s.id}</span></td>
                <td><strong>${s.name}</strong></td>
                <td>${s.email}</td>
                <td>${s.phone || '<span class="text-muted">N/A</span>'}</td>
            `;
            tableBody.appendChild(tr);
        });
    } catch (err) {
        showToast(err.message, "error");
    }
}

async function submitSupplier(event) {
    event.preventDefault();
    const name = document.getElementById("supplier-name").value;
    const email = document.getElementById("supplier-email").value;
    const phone = document.getElementById("supplier-phone").value;

    try {
        const res = await fetch("/api/suppliers", {
            method: 'POST',
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, email, phone })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Failed to register supplier.");
        showToast("Supplier registered successfully", "success");
        closeModal('supplier-modal');
        loadSuppliers();
        preloadFormSelects();
    } catch (err) {
        showToast(err.message, "error");
    }
}

// ==========================================
// Transactions / Audit Logs loading
// ==========================================
async function loadTransactions() {
    try {
        const res = await fetch("/api/transactions?limit=100");
        if (!res.ok) throw new Error("Could not load logs");
        const transactions = await res.json();

        const tableBody = document.getElementById("transactions-table");
        tableBody.innerHTML = "";

        if (transactions.length === 0) {
            tableBody.innerHTML = "<tr><td colspan='7' class='loading-cell'>No logs found in registry</td></tr>";
            return;
        }

        transactions.forEach(tx => {
            const directionBadge = tx.type === 'IN' 
                ? `<span class="badge badge-in"><i class="fa-solid fa-arrow-turn-down"></i> IN</span>`
                : `<span class="badge badge-out"><i class="fa-solid fa-arrow-turn-up"></i> OUT</span>`;
            
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><span class="text-muted">#${tx.id}</span></td>
                <td><span class="badge badge-shipped">${tx.sku}</span></td>
                <td><strong>${tx.product_name}</strong></td>
                <td>${directionBadge}</td>
                <td><strong>${tx.quantity}</strong></td>
                <td>${tx.reason}</td>
                <td class="text-muted">${tx.created_at}</td>
            `;
            tableBody.appendChild(tr);
        });

    } catch (err) {
        showToast(err.message, "error");
    }
}

// ==========================================
// Modal Windows & Form Select Preloaders
// ==========================================
async function preloadFormSelects() {
    try {
        // Preload Customers Select (for Order placement)
        const customersRes = await fetch("/api/customers");
        const customers = await customersRes.json();
        const custSelect = document.getElementById("order-customer");
        custSelect.innerHTML = `<option value="">Choose a customer...</option>` + 
            customers.map(c => `<option value="${c.id}">${c.name} (${c.email})</option>`).join("");

        // Preload Suppliers Select (for Product registration)
        const suppliersRes = await fetch("/api/suppliers");
        const suppliers = await suppliersRes.json();
        const suppSelect = document.getElementById("product-supplier");
        suppSelect.innerHTML = `<option value="">Select a supplier...</option>` + 
            suppliers.map(s => `<option value="${s.id}">${s.name}</option>`).join("");

    } catch (err) {
        console.error("Failed to preload form select elements: " + err);
    }
}

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    modal.classList.add("active");
    
    // Clear form inputs
    const form = modal.querySelector("form");
    if (form) {
        form.reset();
    }

    if (modalId === 'product-modal') {
        // Reset product modal states (restore stock input if previously hidden)
        document.getElementById("product-modal-title").textContent = "Add New Product";
        document.getElementById("product-id-field").value = "";
        document.getElementById("product-sku").disabled = false;
        document.getElementById("product-stock-group").style.display = "block";
        document.getElementById("product-stock").required = true;
    }

    if (modalId === 'order-modal') {
        // Clear order items builder list and insert first input row
        document.getElementById("order-items-container").innerHTML = "";
        addOrderItemField();
    }
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove("active");
}

// Close modals when clicking outside
window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.classList.remove('active');
    }
}

// ==========================================
// Toast Notifications Utilities
// ==========================================
function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;

    let icon = "fa-circle-info";
    if (type === "success") icon = "fa-circle-check";
    else if (type === "error") icon = "fa-circle-exclamation";

    toast.innerHTML = `
        <div class="toast-icon"><i class="fa-solid ${icon}"></i></div>
        <div class="toast-message">${message}</div>
    `;

    container.appendChild(toast);

    // Fade out and remove
    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(50px)";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
