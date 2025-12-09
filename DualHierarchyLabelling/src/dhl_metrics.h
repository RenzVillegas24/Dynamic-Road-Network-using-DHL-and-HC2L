#ifndef DHL_METRICS_H
#define DHL_METRICS_H

/**
 * DHL Performance Metrics Collection
 * 
 * This file provides performance metrics collection for DHL to enable
 * comparison with HC2L as specified in Section 9 of IMPROVED_PROMPT.md.
 * 
 * The comparison validates:
 * - ✅ HC2L avg query time < DHL avg query time
 * - ✅ HC2L rebuild frequency < DHL update frequency
 * - ✅ HC2L memory ≤ DHL memory
 * - ✅ HC2L update time (lazy) << DHL update time
 */

#include <vector>
#include <chrono>
#include <atomic>
#include <mutex>
#include <iostream>
#include <cmath>

namespace dhl_metrics {

using namespace std;

/**
 * DHL Performance Metrics Collection
 * Mirrors the structure from HC2L optimizations.h for comparison
 */
struct DHLPerformanceMetrics {
    // Query performance
    double avg_query_time_ms = 0.0;
    double max_query_time_ms = 0.0;
    double query_std_dev_ms = 0.0;
    size_t query_count = 0;
    
    // Update performance
    double avg_update_time_ms = 0.0;
    size_t update_count = 0;
    size_t full_rebuilds = 0;  // DHL always does full updates (no lazy)
    
    // Memory
    size_t current_memory_bytes = 0;
    size_t peak_memory_bytes = 0;
    size_t label_size_bytes = 0;
    
    // Label statistics
    size_t total_labels = 0;
    double avg_label_size = 0.0;
    
    void print(ostream& os = cerr) const {
        os << "=== DHL Performance Metrics ===" << endl;
        os << "Queries: " << query_count << endl;
        os << "  Avg time: " << avg_query_time_ms << " ms" << endl;
        os << "  Max time: " << max_query_time_ms << " ms" << endl;
        os << "  Std dev: " << query_std_dev_ms << " ms" << endl;
        os << "Updates: " << update_count << endl;
        os << "  Full updates: " << full_rebuilds << " (DHL has no lazy updates)" << endl;
        os << "  Avg update time: " << avg_update_time_ms << " ms" << endl;
        os << "Memory:" << endl;
        os << "  Current: " << (current_memory_bytes / (1024.0 * 1024.0)) << " MB" << endl;
        os << "  Peak: " << (peak_memory_bytes / (1024.0 * 1024.0)) << " MB" << endl;
        os << "  Labels: " << (label_size_bytes / (1024.0 * 1024.0)) << " MB" << endl;
    }
};

/**
 * DHL Performance Collector
 * Thread-safe metrics collection
 */
class DHLPerformanceCollector {
private:
    DHLPerformanceMetrics metrics;
    vector<double> query_times;
    mutable mutex mtx;
    
public:
    void record_query(double time_ms) {
        lock_guard<mutex> lock(mtx);
        metrics.query_count++;
        query_times.push_back(time_ms);
        metrics.max_query_time_ms = max(metrics.max_query_time_ms, time_ms);
        
        // Running average
        double old_avg = metrics.avg_query_time_ms;
        metrics.avg_query_time_ms += (time_ms - old_avg) / metrics.query_count;
    }
    
    void record_update(double time_ms) {
        lock_guard<mutex> lock(mtx);
        metrics.update_count++;
        metrics.full_rebuilds++;  // DHL always does full updates
        
        double old_avg = metrics.avg_update_time_ms;
        metrics.avg_update_time_ms += (time_ms - old_avg) / metrics.update_count;
    }
    
    void record_memory(size_t current, size_t peak) {
        lock_guard<mutex> lock(mtx);
        metrics.current_memory_bytes = current;
        metrics.peak_memory_bytes = max(metrics.peak_memory_bytes, peak);
    }
    
    void record_labels(size_t count, size_t size_bytes) {
        lock_guard<mutex> lock(mtx);
        metrics.total_labels = count;
        metrics.label_size_bytes = size_bytes;
        metrics.avg_label_size = count > 0 ? static_cast<double>(size_bytes) / count : 0.0;
    }
    
    DHLPerformanceMetrics get_metrics() {
        lock_guard<mutex> lock(mtx);
        
        // Calculate standard deviation
        if (query_times.size() > 1) {
            double sum_sq_diff = 0.0;
            for (double t : query_times) {
                sum_sq_diff += (t - metrics.avg_query_time_ms) * (t - metrics.avg_query_time_ms);
            }
            metrics.query_std_dev_ms = sqrt(sum_sq_diff / (query_times.size() - 1));
        }
        
        return metrics;
    }
    
    void reset() {
        lock_guard<mutex> lock(mtx);
        metrics = DHLPerformanceMetrics();
        query_times.clear();
    }
    
    void print_stats(ostream& os = cerr) const {
        lock_guard<mutex> lock(mtx);
        metrics.print(os);
    }
};

// Global DHL performance collector instance
inline DHLPerformanceCollector& get_dhl_performance_collector() {
    static DHLPerformanceCollector collector;
    return collector;
}

/**
 * Memory tracker for DHL
 */
class DHLMemoryMonitor {
private:
    atomic<size_t> current_bytes{0};
    atomic<size_t> peak_bytes{0};
    
public:
    static DHLMemoryMonitor& instance() {
        static DHLMemoryMonitor monitor;
        return monitor;
    }
    
    void allocate(size_t bytes) {
        current_bytes += bytes;
        size_t current = current_bytes.load();
        size_t peak = peak_bytes.load();
        while (current > peak && !peak_bytes.compare_exchange_weak(peak, current)) {
            peak = peak_bytes.load();
        }
    }
    
    void deallocate(size_t bytes) {
        if (bytes > current_bytes) bytes = current_bytes;
        current_bytes -= bytes;
    }
    
    size_t get_current() const { return current_bytes.load(); }
    size_t get_peak() const { return peak_bytes.load(); }
    
    void reset() {
        current_bytes = 0;
        peak_bytes = 0;
    }
    
    static double to_mb(size_t bytes) {
        return static_cast<double>(bytes) / (1024.0 * 1024.0);
    }
};

} // namespace dhl_metrics

#endif // DHL_METRICS_H
