#pragma once

/**
 * Performance Comparison Utility
 * 
 * This file provides utilities for comparing HC2L vs DHL performance
 * as specified in Section 9 of IMPROVED_PROMPT.md.
 * 
 * VALIDATION CHECKLIST:
 * - ✅ HC2L avg query time < DHL avg query time
 * - ✅ HC2L rebuild frequency < DHL update frequency
 * - ✅ HC2L memory ≤ DHL memory
 * - ✅ HC2L update time (lazy) << DHL update time
 */

#ifndef PERFORMANCE_COMPARISON_H
#define PERFORMANCE_COMPARISON_H

#include <string>
#include <vector>
#include <iostream>
#include <fstream>
#include <chrono>
#include <iomanip>

namespace performance_comparison {

using namespace std;

/**
 * Algorithm metrics for comparison
 */
struct AlgorithmMetrics {
    string algorithm_name;
    
    // Query metrics
    size_t query_count = 0;
    double avg_query_time_ms = 0.0;
    double max_query_time_ms = 0.0;
    double query_std_dev_ms = 0.0;
    
    // Update metrics
    size_t update_count = 0;
    size_t lazy_updates = 0;      // HC2L only
    size_t full_rebuilds = 0;     // Both
    double avg_update_time_ms = 0.0;
    double lazy_update_time_ms = 0.0;  // HC2L only
    
    // Memory metrics
    size_t peak_memory_bytes = 0;
    size_t label_size_bytes = 0;
    size_t total_labels = 0;
    
    AlgorithmMetrics(const string& name = "") : algorithm_name(name) {}
};

/**
 * Comparison result with detailed analysis
 */
struct ComparisonResult {
    bool hc2l_outperforms = false;
    
    // Individual metric comparisons
    bool query_time_pass = false;
    bool rebuild_frequency_pass = false;
    bool memory_pass = false;
    bool update_time_pass = false;
    
    // Improvement percentages
    double query_time_improvement_pct = 0.0;
    double memory_reduction_pct = 0.0;
    double update_time_improvement_pct = 0.0;
    
    // Detailed messages
    vector<string> passed_checks;
    vector<string> failed_checks;
    
    string summary_message;
};

/**
 * Compare HC2L and DHL metrics
 */
inline ComparisonResult compare_algorithms(
    const AlgorithmMetrics& hc2l,
    const AlgorithmMetrics& dhl) {
    
    ComparisonResult result;
    
    // 1. Query Time Comparison
    if (dhl.avg_query_time_ms > 0) {
        result.query_time_improvement_pct = 
            ((dhl.avg_query_time_ms - hc2l.avg_query_time_ms) / dhl.avg_query_time_ms) * 100.0;
    }
    
    if (hc2l.avg_query_time_ms < dhl.avg_query_time_ms) {
        result.query_time_pass = true;
        result.passed_checks.push_back(
            "✅ HC2L avg query time < DHL avg query time (" +
            to_string(hc2l.avg_query_time_ms) + "ms vs " +
            to_string(dhl.avg_query_time_ms) + "ms, " +
            to_string(result.query_time_improvement_pct) + "% faster)"
        );
    } else {
        result.failed_checks.push_back(
            "❌ HC2L avg query time >= DHL avg query time (" +
            to_string(hc2l.avg_query_time_ms) + "ms vs " +
            to_string(dhl.avg_query_time_ms) + "ms)"
        );
    }
    
    // 2. Rebuild Frequency Comparison
    double hc2l_rebuild_ratio = hc2l.update_count > 0 ?
        static_cast<double>(hc2l.full_rebuilds) / hc2l.update_count : 0.0;
    double dhl_rebuild_ratio = dhl.update_count > 0 ?
        static_cast<double>(dhl.full_rebuilds) / dhl.update_count : 1.0;  // DHL always full
    
    if (hc2l_rebuild_ratio < dhl_rebuild_ratio) {
        result.rebuild_frequency_pass = true;
        result.passed_checks.push_back(
            "✅ HC2L rebuild frequency < DHL update frequency (" +
            to_string(hc2l_rebuild_ratio * 100) + "% vs " +
            to_string(dhl_rebuild_ratio * 100) + "%)"
        );
    } else {
        result.failed_checks.push_back(
            "❌ HC2L rebuild frequency >= DHL update frequency (" +
            to_string(hc2l_rebuild_ratio * 100) + "% vs " +
            to_string(dhl_rebuild_ratio * 100) + "%)"
        );
    }
    
    // 3. Memory Comparison
    if (dhl.peak_memory_bytes > 0) {
        result.memory_reduction_pct = 
            ((static_cast<double>(dhl.peak_memory_bytes) - hc2l.peak_memory_bytes) / 
             dhl.peak_memory_bytes) * 100.0;
    }
    
    if (hc2l.peak_memory_bytes <= dhl.peak_memory_bytes) {
        result.memory_pass = true;
        result.passed_checks.push_back(
            "✅ HC2L memory ≤ DHL memory (" +
            to_string(hc2l.peak_memory_bytes / (1024*1024)) + "MB vs " +
            to_string(dhl.peak_memory_bytes / (1024*1024)) + "MB)"
        );
    } else {
        result.failed_checks.push_back(
            "❌ HC2L memory > DHL memory (" +
            to_string(hc2l.peak_memory_bytes / (1024*1024)) + "MB vs " +
            to_string(dhl.peak_memory_bytes / (1024*1024)) + "MB)"
        );
    }
    
    // 4. Update Time Comparison (lazy vs full)
    if (dhl.avg_update_time_ms > 0) {
        result.update_time_improvement_pct = 
            ((dhl.avg_update_time_ms - hc2l.lazy_update_time_ms) / dhl.avg_update_time_ms) * 100.0;
    }
    
    // HC2L lazy update should be significantly faster (at least 2x)
    if (hc2l.lazy_update_time_ms < dhl.avg_update_time_ms * 0.5) {
        result.update_time_pass = true;
        result.passed_checks.push_back(
            "✅ HC2L update time (lazy) << DHL update time (" +
            to_string(hc2l.lazy_update_time_ms) + "ms vs " +
            to_string(dhl.avg_update_time_ms) + "ms, " +
            to_string(result.update_time_improvement_pct) + "% faster)"
        );
    } else {
        result.failed_checks.push_back(
            "❌ HC2L lazy update time not significantly faster (" +
            to_string(hc2l.lazy_update_time_ms) + "ms vs " +
            to_string(dhl.avg_update_time_ms) + "ms)"
        );
    }
    
    // Overall result
    result.hc2l_outperforms = result.query_time_pass && 
                               result.rebuild_frequency_pass &&
                               result.memory_pass && 
                               result.update_time_pass;
    
    // Build summary
    result.summary_message = 
        "========================================\n"
        "    HC2L vs DHL PERFORMANCE COMPARISON\n"
        "========================================\n\n";
    
    for (const auto& msg : result.passed_checks) {
        result.summary_message += msg + "\n";
    }
    for (const auto& msg : result.failed_checks) {
        result.summary_message += msg + "\n";
    }
    
    result.summary_message += "\n----------------------------------------\n";
    result.summary_message += "OVERALL: " + 
        string(result.hc2l_outperforms ? "PASS ✅ HC2L outperforms DHL" : "FAIL ❌") + "\n";
    result.summary_message += "----------------------------------------\n";
    
    return result;
}

/**
 * Export comparison results to CSV
 */
inline void export_comparison_csv(
    const string& filename,
    const AlgorithmMetrics& hc2l,
    const AlgorithmMetrics& dhl,
    const ComparisonResult& comparison) {
    
    ofstream out(filename);
    
    // Header
    out << "metric,hc2l,dhl,improvement_pct,pass" << endl;
    
    // Metrics
    out << "avg_query_time_ms," << hc2l.avg_query_time_ms << "," 
        << dhl.avg_query_time_ms << "," 
        << comparison.query_time_improvement_pct << ","
        << (comparison.query_time_pass ? "PASS" : "FAIL") << endl;
    
    out << "max_query_time_ms," << hc2l.max_query_time_ms << ","
        << dhl.max_query_time_ms << ",," << endl;
    
    out << "query_std_dev_ms," << hc2l.query_std_dev_ms << ","
        << dhl.query_std_dev_ms << ",," << endl;
    
    out << "total_queries," << hc2l.query_count << ","
        << dhl.query_count << ",," << endl;
    
    out << "total_updates," << hc2l.update_count << ","
        << dhl.update_count << ",," << endl;
    
    out << "lazy_updates," << hc2l.lazy_updates << ","
        << dhl.lazy_updates << ",," << endl;
    
    out << "full_rebuilds," << hc2l.full_rebuilds << ","
        << dhl.full_rebuilds << ","
        << ((dhl.full_rebuilds > 0) ? 
            ((static_cast<double>(dhl.full_rebuilds - hc2l.full_rebuilds) / dhl.full_rebuilds) * 100) : 0)
        << "," << (comparison.rebuild_frequency_pass ? "PASS" : "FAIL") << endl;
    
    out << "avg_update_time_ms," << hc2l.avg_update_time_ms << ","
        << dhl.avg_update_time_ms << ","
        << comparison.update_time_improvement_pct << ","
        << (comparison.update_time_pass ? "PASS" : "FAIL") << endl;
    
    out << "lazy_update_time_ms," << hc2l.lazy_update_time_ms << ","
        << "N/A" << ",," << endl;
    
    out << "peak_memory_mb," << (hc2l.peak_memory_bytes / (1024.0*1024.0)) << ","
        << (dhl.peak_memory_bytes / (1024.0*1024.0)) << ","
        << comparison.memory_reduction_pct << ","
        << (comparison.memory_pass ? "PASS" : "FAIL") << endl;
    
    out << "label_size_mb," << (hc2l.label_size_bytes / (1024.0*1024.0)) << ","
        << (dhl.label_size_bytes / (1024.0*1024.0)) << ",," << endl;
    
    out << "total_labels," << hc2l.total_labels << ","
        << dhl.total_labels << ",," << endl;
    
    out << "overall_result,," << ","
        << (comparison.hc2l_outperforms ? "PASS" : "FAIL") << endl;
    
    out.close();
}

/**
 * Generate run_metrics.csv as specified in Section 8
 */
inline void export_run_metrics(
    const string& filename,
    int trial_id,
    const string& algorithm,
    int batch_id,
    const AlgorithmMetrics& metrics) {
    
    ofstream out(filename, ios::app);  // Append mode
    
    auto now = chrono::system_clock::now();
    auto time_t_now = chrono::system_clock::to_time_t(now);
    char timestamp[30];
    strftime(timestamp, sizeof(timestamp), "%Y-%m-%dT%H:%M:%S", localtime(&time_t_now));
    
    // trial_id,algorithm,batch_id,phase,metric_name,value,unit,timestamp
    
    // Query metrics
    out << trial_id << "," << algorithm << "," << batch_id << ",QUERY,avg_query_time,"
        << metrics.avg_query_time_ms << ",ms," << timestamp << endl;
    out << trial_id << "," << algorithm << "," << batch_id << ",QUERY,query_std_dev,"
        << metrics.query_std_dev_ms << ",ms," << timestamp << endl;
    out << trial_id << "," << algorithm << "," << batch_id << ",QUERY,query_count,"
        << metrics.query_count << ",count," << timestamp << endl;
    
    // Update metrics
    out << trial_id << "," << algorithm << "," << batch_id << ",UPDATE,avg_update_time,"
        << metrics.avg_update_time_ms << ",ms," << timestamp << endl;
    if (algorithm == "HC2L") {
        out << trial_id << "," << algorithm << "," << batch_id << ",UPDATE,lazy_update_time,"
            << metrics.lazy_update_time_ms << ",ms," << timestamp << endl;
    }
    out << trial_id << "," << algorithm << "," << batch_id << ",UPDATE,full_rebuilds,"
        << metrics.full_rebuilds << ",count," << timestamp << endl;
    
    // Memory metrics
    out << trial_id << "," << algorithm << "," << batch_id << ",MEMORY,peak_memory,"
        << (metrics.peak_memory_bytes / (1024.0 * 1024.0)) << ",MB," << timestamp << endl;
    out << trial_id << "," << algorithm << "," << batch_id << ",MEMORY,label_size,"
        << (metrics.label_size_bytes / (1024.0 * 1024.0)) << ",MB," << timestamp << endl;
    
    out.close();
}

} // namespace performance_comparison

#endif // PERFORMANCE_COMPARISON_H
