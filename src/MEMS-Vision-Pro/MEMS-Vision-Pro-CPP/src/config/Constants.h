#ifndef CONSTANTS_H
#define CONSTANTS_H

#include <cstdint>

namespace Config {

// 网络配置
constexpr uint16_t UDP_PORT_CH1 = 0x8001;      // 通道1端口
constexpr uint16_t UDP_PORT_CH2 = 0x8000;      // 通道2端口（与Python版本一致）
constexpr uint16_t UDP_CONTROL_PORT = 0x8004;  // 控制命令端口
constexpr int UDP_BUFFER_SIZE = 65535;         // UDP缓冲区大小
constexpr int SOCKET_RECV_BUFFER = 16 * 1024 * 1024;  // 16MB接收缓冲

// 队列配置
constexpr int QUEUE_MAX_SIZE = 10000;          // 最大队列长度

// 图像参数
constexpr int IMAGE_SIZE = 512;                // 图像尺寸 512x512
constexpr int NUM_FRAME = 1000000;             // 采样点数
constexpr double SAMPLE_RATE = 1e7;            // 采样率 10MHz

// 协议常量
constexpr uint16_t FRAME_HEADER_MAGIC = 0x2AFF;   // 帧头标识
constexpr uint16_t PACKET_HEADER_MAGIC = 0x2CFF;  // 数据包标识

// 默认频率参数
constexpr double DEFAULT_FREQ_X = 200.0;
constexpr double DEFAULT_FREQ_Y = 233.0;
constexpr double DEFAULT_PHASE_X = 0.0;
constexpr double DEFAULT_PHASE_Y = 0.0;

// 性能参数
constexpr int MAX_PROCESSORS_PER_CHANNEL = 1;  // 每通道最大处理器数
constexpr double MIN_FRAME_INTERVAL = 0.05;    // 最小帧间隔 50ms (20fps)
constexpr int FRAME_TIMEOUT_MS = 500;          // 帧超时 500ms

}  // namespace Config

#endif  // CONSTANTS_H
