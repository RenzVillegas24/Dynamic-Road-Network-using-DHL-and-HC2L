/**
 * Logging System Module
 * Real-time event logging for Developer View
 * Tracks all system events, route calculations, traffic updates, etc.
 */

// Log levels
const LogLevel = {
    DEBUG: { name: 'DEBUG', color: '#6b7280', icon: '🔧', bgColor: 'bg-gray-100' },
    INFO: { name: 'INFO', color: '#3b82f6', icon: 'ℹ️', bgColor: 'bg-blue-100' },
    SUCCESS: { name: 'SUCCESS', color: '#10b981', icon: '✅', bgColor: 'bg-green-100' },
    WARNING: { name: 'WARN', color: '#f59e0b', icon: '⚠️', bgColor: 'bg-yellow-100' },
    ERROR: { name: 'ERROR', color: '#ef4444', icon: '❌', bgColor: 'bg-red-100' },
    QUERY: { name: 'QUERY', color: '#8b5cf6', icon: '🔍', bgColor: 'bg-purple-100' },
    UPDATE: { name: 'UPDATE', color: '#06b6d4', icon: '🔄', bgColor: 'bg-cyan-100' }
};

// Logging system state
const LoggingSystem = {
    logs: [],
    maxLogs: 500,  // Limit logs to prevent memory issues
    isEnabled: true,
    autoScroll: true,
    consoleInterceptionEnabled: false,  // Disabled by default to prevent slowdown
    filters: {
        debug: true,
        info: true,
        success: true,
        warning: true,
        error: true,
        query: true,
        update: true
    }
};

/**
 * Add a log entry
 */
function addLog(message, level = LogLevel.INFO, metadata = {}) {
    const log = {
        id: Date.now() + Math.random(),
        timestamp: Date.now(),
        formattedTime: new Date().toLocaleTimeString('en-US', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit',
            fractionalSecondDigits: 3
        }),
        message,
        level,
        metadata
    };
    
    LoggingSystem.logs.push(log);
    
    // Limit logs to prevent memory issues
    if (LoggingSystem.logs.length > LoggingSystem.maxLogs) {
        LoggingSystem.logs.shift();  // Remove oldest log
    }
    
    updateLogDisplay();
}

/**
 * Format log timestamp
 */
function formatLogTime(date) {
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    const ms = String(date.getMilliseconds()).padStart(3, '0');
    return `${hours}:${minutes}:${seconds}.${ms}`;
}

/**
 * Update log display in UI
 */
function updateLogDisplay() {
    const logContainer = document.getElementById('log-entries-container');
    if (!logContainer) return;
    
    // Filter logs based on active filters
    const filteredLogs = LoggingSystem.logs.filter(log => {
        const filterKey = log.level.name.toLowerCase();
        return LoggingSystem.filters[filterKey] !== false;
    });
    
    // Build HTML for visible logs (only show last 100 for performance)
    const visibleLogs = filteredLogs.slice(0, 100);
    logContainer.innerHTML = visibleLogs.map(log => createLogEntryHTML(log)).join('');
    
    // Re-create lucide icons for the new log entries
    if (typeof lucide !== 'undefined') {
        lucide.createIcons();
    }
    
    // Auto-scroll to newest (top)
    if (LoggingSystem.autoScroll) {
        logContainer.scrollTop = 0;
    }
}

/**
 * Create HTML for a single log entry (collapsible dark theme)
 */
function createLogEntryHTML(log) {
    const hasMetadata = Object.keys(log.metadata).length > 0;
    const entryId = `log-${log.id}`;
    
    // Determine source indicator
    const isBackendLog = log.message.includes('[Backend]');
    const isConsoleLog = log.message.includes('[Console]');
    let sourceClass = '';
    let sourceLabel = '';
    
    if (isBackendLog) {
        sourceClass = 'log-entry__source--backend';
        sourceLabel = 'PY';
    } else if (isConsoleLog) {
        sourceClass = 'log-entry__source--console';
        sourceLabel = 'JS';
    }
    
    // Get level class
    const levelClass = `log-entry__badge--${log.level.name.toLowerCase()}`;
    
    // Truncate message for preview (max 80 chars)
    const fullMessage = log.message;
    const previewMessage = fullMessage.length > 80 ? fullMessage.substring(0, 80) + '...' : fullMessage;
    const needsExpand = fullMessage.length > 80 || hasMetadata;
    
    // Build metadata section
    let metadataSection = '';
    if (hasMetadata) {
        metadataSection = `
            <div class="mt-2 pt-2 border-t border-gray-700">
                <div class="text-xs text-gray-500 mb-1">Metadata:</div>
                <pre class="text-xs text-gray-400">${JSON.stringify(log.metadata, null, 2)}</pre>
            </div>
        `;
    }
    
    if (needsExpand) {
        return `
            <div class="log-entry log-entry--collapsible" id="${entryId}" onclick="toggleLogEntry('${entryId}')">
                <div class="log-entry__header">
                    <div class="log-entry__expand">
                        <i data-lucide="chevron-right" class="w-3 h-3"></i>
                    </div>
                    <span class="log-entry__time">${log.formattedTime}</span>
                    <span class="log-entry__badge ${levelClass}">${log.level.name}</span>
                    ${sourceLabel ? `<span class="log-entry__source ${sourceClass}">${sourceLabel}</span>` : ''}
                    <span class="log-entry__preview">${escapeHTML(previewMessage)}</span>
                </div>
                <div class="log-entry__full">
                    ${escapeHTML(fullMessage)}
                    ${metadataSection}
                </div>
            </div>
        `;
    } else {
        return `
            <div class="log-entry" id="${entryId}">
                <span class="log-entry__time">${log.formattedTime}</span>
                <span class="log-entry__level log-entry__level--${log.level.name.toLowerCase()}">${log.level.name}</span>
                ${sourceLabel ? `<span class="log-entry__source ${sourceClass}">${sourceLabel}</span>` : ''}
                <span class="log-entry__message">${escapeHTML(fullMessage)}</span>
            </div>
        `;
    }
}

/**
 * Toggle log entry expansion
 */
function toggleLogEntry(id) {
    const element = document.getElementById(id);
    if (element) {
        element.classList.toggle('log-entry--expanded');
        // Re-create lucide icons after toggle
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    }
}

/**
 * Clear all logs
 */
function clearLogs() {
    LoggingSystem.logs = [];
    updateLogDisplay();
    addLog('Logs cleared', LogLevel.INFO);
}

/**
 * Export logs to JSON file
 */
function exportLogs() {
    const dataStr = JSON.stringify(LoggingSystem.logs, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `system-logs-${new Date().toISOString()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    addLog('Logs exported successfully', LogLevel.SUCCESS);
}

/**
 * Toggle log filter
 */
function toggleLogFilter(filterName) {
    LoggingSystem.filters[filterName] = !LoggingSystem.filters[filterName];
    updateLogDisplay();
    
    // Update UI checkbox
    const checkbox = document.getElementById(`filter-${filterName}`);
    if (checkbox) {
        checkbox.checked = LoggingSystem.filters[filterName];
    }
}

/**
 * Helper to escape HTML
 */
function escapeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/**
 * Convenience logging functions
 */
window.logDebug = (msg, meta) => addLog(msg, LogLevel.DEBUG, meta);
window.logInfo = (msg, meta) => addLog(msg, LogLevel.INFO, meta);
window.logSuccess = (msg, meta) => addLog(msg, LogLevel.SUCCESS, meta);
window.logWarning = (msg, meta) => addLog(msg, LogLevel.WARNING, meta);
window.logError = (msg, meta) => addLog(msg, LogLevel.ERROR, meta);
window.logQuery = (msg, meta) => addLog(msg, LogLevel.QUERY, meta);
window.logUpdate = (msg, meta) => addLog(msg, LogLevel.UPDATE, meta);

/**
 * Intercept console logs and add to logging system
 * WARNING: This can cause performance issues if too many console logs are generated
 */
function interceptConsoleLogs() {
    if (LoggingSystem.consoleInterceptionEnabled) {
        return;  // Already enabled
    }
    
    // Store original console methods globally
    if (!window.originalConsole) {
        window.originalConsole = {
            log: console.log,
            info: console.info,
            warn: console.warn,
            error: console.error,
            debug: console.debug
        };
    }
    
    const originalConsole = window.originalConsole;
    
    // Intercept console.log
    console.log = function(...args) {
        originalConsole.log.apply(console, args);
        // Prevent infinite loops by checking if message is already from logging system
        const firstArg = args[0];
        if (typeof firstArg === 'string' && firstArg.includes('[Console]')) {
            return;
        }
        const message = args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' ');
        addLog(`[Console] ${message}`, LogLevel.DEBUG);
    };
    
    // Intercept console.info
    console.info = function(...args) {
        originalConsole.info.apply(console, args);
        const firstArg = args[0];
        if (typeof firstArg === 'string' && firstArg.includes('[Console]')) {
            return;
        }
        const message = args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' ');
        addLog(`[Console] ${message}`, LogLevel.INFO);
    };
    
    // Intercept console.warn
    console.warn = function(...args) {
        originalConsole.warn.apply(console, args);
        const message = args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' ');
        addLog(`[Console] ${message}`, LogLevel.WARNING);
    };
    
    // Intercept console.error
    console.error = function(...args) {
        originalConsole.error.apply(console, args);
        const message = args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' ');
        const metadata = {};
        
        // Extract error stack if available
        args.forEach((arg, i) => {
            if (arg instanceof Error) {
                metadata[`error_${i}`] = {
                    message: arg.message,
                    stack: arg.stack
                };
            }
        });
        
        addLog(`[Console] ${message}`, LogLevel.ERROR, metadata);
    };
    
    // Intercept console.debug
    console.debug = function(...args) {
        originalConsole.debug.apply(console, args);
        const message = args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' ');
        addLog(`[Console] ${message}`, LogLevel.DEBUG);
    };
    
    // Store original console for direct access if needed
    window.originalConsole = originalConsole;
    
    addLog('Console interception enabled', LogLevel.SUCCESS);
}

/**
 * Poll Python backend logs
 */
let backendLogPolling = null;
let lastBackendLogTimestamp = 0;

async function pollBackendLogs() {
    try {
        const response = await fetch(`/get_backend_logs?since=${lastBackendLogTimestamp}`);
        const data = await response.json();
        
        if (data.success && data.logs && data.logs.length > 0) {
            // Batch add logs to improve performance
            const logsToAdd = data.logs.map(log => {
                const level = parseBackendLogLevel(log.level);
                const message = `[Backend] ${log.message}`;
                
                // Update last timestamp
                if (log.timestamp > lastBackendLogTimestamp) {
                    lastBackendLogTimestamp = log.timestamp;
                }
                
                return {
                    message,
                    level,
                    metadata: {
                        source: 'python',
                        module: log.module || 'unknown',
                        line: log.line || 0,
                        timestamp: log.timestamp
                    }
                };
            });
            
            // Add all logs at once
            logsToAdd.forEach(({message, level, metadata}) => {
                addLog(message, level, metadata);
            });
        }
    } catch (error) {
        // Silently fail - backend logging is optional
        if (window.originalConsole) {
            window.originalConsole.debug('Backend log polling error:', error);
        }
    }
}

function parseBackendLogLevel(level) {
    const levelMap = {
        'DEBUG': LogLevel.DEBUG,
        'INFO': LogLevel.INFO,
        'WARNING': LogLevel.WARNING,
        'ERROR': LogLevel.ERROR,
        'CRITICAL': LogLevel.ERROR,
        'SUCCESS': LogLevel.SUCCESS
    };
    
    return levelMap[level?.toUpperCase()] || LogLevel.INFO;
}

function startBackendLogPolling(intervalMs = 5000) {  // Increased to 5 seconds to reduce load
    if (backendLogPolling) {
        clearInterval(backendLogPolling);
    }
    
    backendLogPolling = setInterval(pollBackendLogs, intervalMs);
    addLog('Backend log polling started (every ' + (intervalMs/1000) + 's)', LogLevel.SUCCESS);
}

function stopBackendLogPolling() {
    if (backendLogPolling) {
        clearInterval(backendLogPolling);
        backendLogPolling = null;
        addLog('Backend log polling stopped', LogLevel.INFO);
    }
}

// Expose functions globally
window.LoggingSystem = LoggingSystem;
window.addLog = addLog;
window.clearLogs = clearLogs;
window.exportLogs = exportLogs;
window.toggleLogEntry = toggleLogEntry;
window.toggleLogFilter = toggleLogFilter;
window.updateLogDisplay = updateLogDisplay;
window.interceptConsoleLogs = interceptConsoleLogs;
window.restoreConsoleLogs = restoreConsoleLogs;
window.startBackendLogPolling = startBackendLogPolling;
window.stopBackendLogPolling = stopBackendLogPolling;

// Initialize with welcome message
addLog('Logging system initialized', LogLevel.SUCCESS);

// Console interception is now MANUAL - users must enable it via UI to prevent slowdown
// interceptConsoleLogs();  // DISABLED by default

console.log('✅ Logging system module loaded');
