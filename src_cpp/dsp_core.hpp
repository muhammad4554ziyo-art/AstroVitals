/**
 * @file dsp_core.hpp
 * @brief High-Performance C++ DSP Core & SEU Radiation Hardening Engine
 * 
 * Implements real-time Kalman filtering with dynamic IMU-correlated motion
 * artifact rejection, IEEE 802.3 CRC32 integrity validation, and Triple Modular
 * Redundancy (TMR) for cosmic-radiation Single-Event Upset (SEU) mitigation.
 */

#ifndef DSP_CORE_HPP
#define DSP_CORE_HPP

#include <cstdint>
#include <cstddef>
#include <cmath>
#include <array>
#include <vector>
#include <algorithm>

namespace astronaut {

/**
 * @brief IEEE 802.3 Standard CRC-32 Calculator
 */
class CRC32 {
public:
    static uint32_t calculate(const uint8_t* data, size_t length);
    static bool verify(const uint8_t* data, size_t length, uint32_t expected_crc);

private:
    static const uint32_t TABLE[256];
};

/**
 * @brief 1D Adaptive Kalman Filter with Dynamic Motion Noise Scaling
 * 
 * Adapts measurement covariance R based on real-time 3-axis accelerometer jerk / vibration:
 * R_eff = R_base * (1.0 + motion_alpha * (motion_magnitude ^ 2))
 */
class AdaptiveKalmanFilter {
public:
    AdaptiveKalmanFilter(double initial_state = 70.0,
                         double initial_p = 10.0,
                         double q = 0.05,
                         double r_base = 2.0,
                         double motion_alpha = 3.5);

    double update(double measurement, double motion_intensity);
    double get_state() const { return state_; }
    double get_covariance() const { return p_; }
    void reset(double new_state);

private:
    double state_;        ///< State estimate (x)
    double p_;            ///< Estimation error covariance (P)
    double q_;            ///< Process noise covariance (Q)
    double r_base_;       ///< Base measurement noise covariance (R_base)
    double motion_alpha_; ///< Scaling sensitivity to accelerometer motion
};

/**
 * @brief Triple Modular Redundancy (TMR) Memory Container
 * 
 * Protects mission-critical parameters (e.g. oxygen flow rate, alert states)
 * against single-event upsets (SEU) caused by solar particle events (SPE)
 * and galactic cosmic rays (GCR).
 */
template <typename T>
class TMRProtected {
public:
    explicit TMRProtected(T initial_value) : seu_repairs_count_(0) {
        copies_[0] = initial_value;
        copies_[1] = initial_value;
        copies_[2] = initial_value;
    }

    T get() {
        if (copies_[0] == copies_[1]) {
            if (copies_[0] != copies_[2]) {
                // Bit-flip in copies_[2] detected -> self-heal
                copies_[2] = copies_[0];
                ++seu_repairs_count_;
            }
            return copies_[0];
        } else if (copies_[0] == copies_[2]) {
            // Bit-flip in copies_[1] detected -> self-heal
            copies_[1] = copies_[0];
            ++seu_repairs_count_;
            return copies_[0];
        } else if (copies_[1] == copies_[2]) {
            // Bit-flip in copies_[0] detected -> self-heal
            copies_[0] = copies_[1];
            ++seu_repairs_count_;
            return copies_[1];
        }
        // Catastrophic double-fault: Fallback to majority or copy 0
        return copies_[0];
    }

    void set(T new_value) {
        copies_[0] = new_value;
        copies_[1] = new_value;
        copies_[2] = new_value;
    }

    uint64_t get_seu_repairs_count() const {
        return seu_repairs_count_;
    }

    // Radiation fault simulation helper
    void inject_bitflip(size_t replica_index, size_t bit_index) {
        if (replica_index < 3 && bit_index < (sizeof(T) * 8)) {
            uint8_t* byte_ptr = reinterpret_cast<uint8_t*>(&copies_[replica_index]);
            size_t byte_idx = bit_index / 8;
            size_t bit_in_byte = bit_index % 8;
            byte_ptr[byte_idx] ^= (1 << bit_in_byte);
        }
    }

private:
    std::array<T, 3> copies_;
    uint64_t seu_repairs_count_;
};

} // namespace astronaut

// C-compatible ABI exports for Python ctypes integration
extern "C" {
    void* dsp_kalman_create(double init_state, double init_p, double q, double r_base, double motion_alpha);
    double dsp_kalman_update(void* handle, double measurement, double motion_intensity);
    double dsp_kalman_get_state(void* handle);
    void dsp_kalman_destroy(void* handle);

    uint32_t dsp_crc32_calculate(const uint8_t* data, size_t length);
    int dsp_crc32_verify(const uint8_t* data, size_t length, uint32_t expected_crc);

    void* dsp_tmr_int_create(int32_t initial_val);
    int32_t dsp_tmr_int_get(void* handle);
    void dsp_tmr_int_set(void* handle, int32_t new_val);
    uint64_t dsp_tmr_int_repairs(void* handle);
    void dsp_tmr_int_inject_bitflip(void* handle, size_t replica, size_t bit_idx);
    void dsp_tmr_int_destroy(void* handle);
}

#endif // DSP_CORE_HPP
