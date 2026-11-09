/**
 * @file main_dsp.cpp
 * @brief Standalone Verification & Benchmark for C++ DSP Core & SEU TMR
 */

#include "dsp_core.hpp"
#include <iostream>
#include <vector>
#include <chrono>
#include <cassert>
#include <random>

int main() {
    std::cout << "====================================================\n";
    std::cout << "  Deep-Space Astronaut Health DSP & SEU Core Benchmark\n";
    std::cout << "====================================================\n";

    // 1. Verify CRC32
    const char* test_str = "ASTRONAUT_TELEMETRY_PACKET_TEST_PAYLOAD";
    uint32_t crc = astronaut::CRC32::calculate(reinterpret_cast<const uint8_t*>(test_str), 39);
    bool valid = astronaut::CRC32::verify(reinterpret_cast<const uint8_t*>(test_str), 39, crc);
    std::cout << "[1] CRC-32 Test: 0x" << std::hex << crc << std::dec 
              << " | Verification: " << (valid ? "PASSED" : "FAILED") << "\n";
    assert(valid);

    // 2. Verify Triple Modular Redundancy (TMR) SEU Auto-Repair
    std::cout << "[2] Triple Modular Redundancy (TMR) Bit-Flip Test...\n";
    astronaut::TMRProtected<int32_t> suit_o2_flow(100); // 100% nominal O2
    assert(suit_o2_flow.get() == 100);

    // Simulate Cosmic Ray SPE particle striking replica 1 and flipping bit 2
    suit_o2_flow.inject_bitflip(1, 2);
    int32_t healed_value = suit_o2_flow.get();
    std::cout << "    Injected SEU bit-flip in Replica 1. Read value: " << healed_value
              << " | SEU Auto-Repairs: " << suit_o2_flow.get_seu_repairs_count() << "\n";
    assert(healed_value == 100);
    assert(suit_o2_flow.get_seu_repairs_count() == 1);

    // 3. Motion Artifact Rejection Benchmark with Adaptive Kalman Filter
    std::cout << "[3] Running 1,000,000 Sample Kalman Motion Rejection Benchmark...\n";
    astronaut::AdaptiveKalmanFilter kf(75.0, 5.0, 0.05, 1.5, 5.0);

    std::mt19937_64 rng(42);
    std::normal_distribution<double> sensor_noise(0.0, 2.0);
    std::uniform_real_distribution<double> motion_dist(0.0, 8.0); // 0 to 8 m/s^2 vibration

    auto start_time = std::chrono::high_resolution_clock::now();
    double filtered_val = 75.0;
    for (int i = 0; i < 1000000; ++i) {
        double motion = motion_dist(rng);
        double measurement = 75.0 + sensor_noise(rng) + (motion > 3.0 ? (motion * 5.0) : 0.0);
        filtered_val = kf.update(measurement, motion);
    }
    auto end_time = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double, std::milli> elapsed_ms = end_time - start_time;

    std::cout << "    Processed 1,000,000 samples in: " << elapsed_ms.count() << " ms\n";
    std::cout << "    Throughput: " << (1000.0 / elapsed_ms.count()) << " Million samples/sec\n";
    std::cout << "    Latency per sample: " << (elapsed_ms.count() * 1000.0 / 1000000.0) << " nanoseconds\n";
    std::cout << "    Final filtered state: " << filtered_val << " bpm\n";
    std::cout << "[+] All C++ Core verification and benchmark assertions PASSED!\n";

    return 0;
}
