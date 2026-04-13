#include "ImageProtocolParsing.h"

#include <algorithm>

uint32_t ImageProtocolParsing::readLittleEndianU32(const uint8_t* data) {
    return static_cast<uint32_t>(data[0]) |
           (static_cast<uint32_t>(data[1]) << 8) |
           (static_cast<uint32_t>(data[2]) << 16) |
           (static_cast<uint32_t>(data[3]) << 24);
}

uint16_t ImageProtocolParsing::readBigEndianU16(const uint8_t* data) {
    return static_cast<uint16_t>(data[0] << 8) |
           static_cast<uint16_t>(data[1]);
}

uint16_t ImageProtocolParsing::readBigEndianU16Payload(const uint8_t* data) {
    return static_cast<uint16_t>(data[0] << 8) |
           static_cast<uint16_t>(data[1]);
}

ParsedFrameHeader ImageProtocolParsing::parseFrameHeader(const QByteArray& headerPacket) {
    ParsedFrameHeader parsed;

    if (headerPacket.size() < 16) {
        return parsed;
    }

    const auto* data = reinterpret_cast<const uint8_t*>(headerPacket.constData());
    parsed.valid = true;
    parsed.frameId = readBigEndianU16(data + 2);
    parsed.samplePoint = readLittleEndianU32(data + 4);
    parsed.phaseX = readLittleEndianU32(data + 8);
    parsed.phaseY = readLittleEndianU32(data + 12);

    if (parsed.samplePoint > 2000000u) {
        parsed.samplePoint = 1000000u;
    }

    return parsed;
}

std::vector<uint16_t> ImageProtocolParsing::extractGrayValues(const std::vector<QByteArray>& packets) {
    std::vector<uint16_t> grayValues;

    for (size_t i = 0; i < packets.size(); ++i) {
        const auto& packet = packets[i];
        const auto* data = reinterpret_cast<const uint8_t*>(packet.constData());
        const int size = packet.size();

        const int offset = (i == 0) ? 16 : 4;
        for (int j = offset; j + 1 < size; j += 2) {
            const uint16_t raw = readBigEndianU16Payload(data + j);
            grayValues.push_back(static_cast<uint16_t>(65535u - raw));
        }
    }

    return grayValues;
}
