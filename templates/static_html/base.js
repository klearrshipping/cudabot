// Resizable panels functionality
let isResizing = false;

const resizer = document.getElementById('resizer');
const leftPanel = document.getElementById('leftPanel');
const container = document.querySelector('.main-content');

if (resizer && leftPanel && container) {
    resizer.addEventListener('mousedown', (e) => {
        isResizing = true;
        resizer.classList.add('dragging');
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
        e.preventDefault();
    });
}

function handleMouseMove(e) {
    if (!isResizing) return;
    
    const containerRect = container.getBoundingClientRect();
    const percentage = ((e.clientX - containerRect.left) / containerRect.width) * 100;
    
    // Limit the resize between 20% and 80%
    if (percentage >= 20 && percentage <= 80) {
        leftPanel.style.width = percentage + '%';
    }
}

function handleMouseUp() {
    isResizing = false;
    if (resizer) {
        resizer.classList.remove('dragging');
    }
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
}

// Chat functionality
function sendMessage() {
    const input = document.getElementById('chatInput');
    const messages = document.getElementById('chatMessages');
    
    if (input && messages && input.value.trim()) {
        // Add user message
        const userMessage = document.createElement('div');
        userMessage.className = 'message user';
        userMessage.textContent = input.value;
        messages.appendChild(userMessage);
        
        // Clear input
        input.value = '';
        
        // Scroll to bottom
        messages.scrollTop = messages.scrollHeight;
        
        // Simulate AI response (you would replace this with actual AI integration)
        setTimeout(() => {
            const aiMessage = document.createElement('div');
            aiMessage.className = 'message assistant';
            aiMessage.textContent = "I understand! Let me help you with that. This is a simulated response - in a real implementation, this would connect to an AI service.";
            messages.appendChild(aiMessage);
            messages.scrollTop = messages.scrollHeight;
        }, 1000);
    }
}

// Handle Enter key in chat input
document.addEventListener('DOMContentLoaded', function() {
    const chatInput = document.getElementById('chatInput');
    if (chatInput) {
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
});

// File/navigation item selection
function initializeNavigation() {
    document.querySelectorAll('.file-item, .nav-item').forEach(item => {
        item.addEventListener('click', () => {
            // Remove active class from all items
            document.querySelectorAll('.file-item, .nav-item').forEach(i => i.classList.remove('active'));
            // Add active class to clicked item
            item.classList.add('active');
        });
    });
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeNavigation();
});

// Utility functions for CUDA system
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 16px;
        border-radius: 4px;
        color: white;
        font-size: 13px;
        z-index: 1000;
        opacity: 0;
        transition: opacity 0.3s ease;
    `;
    
    // Set background color based on type
    switch(type) {
        case 'success':
            notification.style.background = '#0e4429';
            break;
        case 'error':
            notification.style.background = '#8b0000';
            break;
        case 'warning':
            notification.style.background = '#8b4513';
            break;
        default:
            notification.style.background = '#007acc';
    }
    
    document.body.appendChild(notification);
    
    // Animate in
    setTimeout(() => {
        notification.style.opacity = '1';
    }, 10);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }, 3000);
}

// API helper functions
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('API request failed:', error);
        showNotification('API request failed: ' + error.message, 'error');
        throw error;
    }
}

// Form helper functions
function serializeForm(form) {
    const formData = new FormData(form);
    const data = {};
    for (let [key, value] of formData.entries()) {
        data[key] = value;
    }
    return data;
}

function validateForm(form, rules = {}) {
    const errors = {};
    const formData = new FormData(form);
    
    for (const [field, rule] of Object.entries(rules)) {
        const value = formData.get(field);
        
        if (rule.required && (!value || value.trim() === '')) {
            errors[field] = `${field} is required`;
        }
        
        if (rule.minLength && value && value.length < rule.minLength) {
            errors[field] = `${field} must be at least ${rule.minLength} characters`;
        }
        
        if (rule.pattern && value && !rule.pattern.test(value)) {
            errors[field] = `${field} format is invalid`;
        }
    }
    
    return {
        isValid: Object.keys(errors).length === 0,
        errors
    };
}
