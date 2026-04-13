#ifndef IMAGE_PROTOCOL_PARSING_H
#define IMAGE_PROTOCOL_PARSING_H

#include <QByteArray>
#include <cstdint>
#include <vector>

struct ParsedFrameHeader {
    bool valid = false;
    uint16_t frameId = 0;
    uint32_t samplePoint = 0;
    uint32_t phaseX = 0;
    uint32_t phaseY = 0;
};

class ImageProtocolParsing {
public:
    static ParsedFrameHeader parseFrameHeader(const QByteArray& headerPacket);
    static std::vector<uint16_t> extractGrayValues(const std::vector<QByteArray>& packets);

private:
    static uint32_t readLittleEndianU32(const uint8_t* data);
    static uint16_t readBigEndianU16(const uint8_t* data);
    static uint16_t readBigEndianU16Payload(const uint8_t* data);
};

#endif  // IMAGE_PROTOCOL_PARSING_H
