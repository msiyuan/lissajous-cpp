#include "processing/ImageProtocolParsing.h"
#include "TestSupport.h"
#include <QByteArray>
#include <cstdio>

namespace {

void test_parse_standard_28_byte_header() {
    // Build a standard 28-byte frame header
    // Format: 0x2AFF(2) + FrameCnt(2) + SamplePoint(4) + PhaseX(4) + PhaseY(4)
    //         + phaseFrameId(4) + phaseIndex(1) + frameStatus(1) + currentXInitialPhase(2)
    //         + currentYInitialPhase(2) + phaseCount(1) + fixedZero(1)
    uint8_t data[28] = {0};

    // Magic: 0x2AFF (big endian at offset 0-1)
    data[0] = 0x2A;
    data[1] = 0xFF;

    // Frame counter: 0x0001 (big endian at offset 2-3)
    data[2] = 0x00;
    data[3] = 0x01;

    // Sample point: 1000000 (0x000F4240, little endian at offset 4-7)
    data[4] = 0x40;
    data[5] = 0x42;
    data[6] = 0x0F;
    data[7] = 0x00;

    // Phase X: 0 (little endian at offset 8-11)
    data[8] = 0x00;
    data[9] = 0x00;
    data[10] = 0x00;
    data[11] = 0x00;

    // Phase Y: 45000000 (0x02AEA540, little endian at offset 12-15)
    // 45000000 = 0x02AEA540 = bytes [40, A5, AE, 02]
    data[12] = 0x40;  // byte 0 (LSB)
    data[13] = 0xA5;  // byte 1
    data[14] = 0xAE;  // byte 2
    data[15] = 0x02;  // byte 3 (MSB)

    // Phase frame ID: 100 (little endian at offset 16-19)
    data[16] = 0x64;
    data[17] = 0x00;
    data[18] = 0x00;
    data[19] = 0x00;

    // Phase index: 1 (at offset 20)
    data[20] = 0x01;

    // Frame status: 1 (normal, at offset 21)
    data[21] = 0x01;

    // Current X initial phase: 0 (little endian at offset 22-23)
    data[22] = 0x00;
    data[23] = 0x00;

    // Current Y initial phase: 4500 = 450.0 degrees (little endian at offset 24-25)
    data[24] = 0x94;
    data[25] = 0x11;

    // Phase count: 3 (at offset 26)
    data[26] = 0x03;

    // Fixed zero (at offset 27)
    data[27] = 0x00;

    QByteArray header(reinterpret_cast<char*>(data), 28);
    ParsedFrameHeader parsed = ImageProtocolParsing::parseFrameHeader(header);

    REQUIRE(parsed.valid == true);
    REQUIRE(parsed.frameId == 0x0001);
    REQUIRE(parsed.samplePoint == 1000000);
    REQUIRE(parsed.phaseX == 0);
    REQUIRE(parsed.phaseY == 45000000);
    REQUIRE(parsed.phaseFrameId == 100);
    REQUIRE(parsed.phaseIndex == 1);
    REQUIRE(parsed.frameStatus == 1);
    REQUIRE(parsed.currentXInitialPhase == 0);
    REQUIRE(parsed.currentYInitialPhase == 4500);
    REQUIRE(parsed.phaseCount == 3);
}

void test_parse_phase_index_values() {
    // Test phase_index = 0
    {
        uint8_t data[28] = {0};
        data[0] = 0x2A; data[1] = 0xFF;
        data[20] = 0x00;  // phaseIndex = 0
        data[21] = 0x01;  // frameStatus = 1 (normal)
        data[26] = 0x03;  // phaseCount = 3

        QByteArray header(reinterpret_cast<char*>(data), 28);
        ParsedFrameHeader parsed = ImageProtocolParsing::parseFrameHeader(header);
        REQUIRE(parsed.phaseIndex == 0);
    }

    // Test phase_index = 1
    {
        uint8_t data[28] = {0};
        data[0] = 0x2A; data[1] = 0xFF;
        data[20] = 0x01;  // phaseIndex = 1
        data[21] = 0x01;  // frameStatus = 1 (normal)
        data[26] = 0x03;  // phaseCount = 3

        QByteArray header(reinterpret_cast<char*>(data), 28);
        ParsedFrameHeader parsed = ImageProtocolParsing::parseFrameHeader(header);
        REQUIRE(parsed.phaseIndex == 1);
    }

    // Test phase_index = 2
    {
        uint8_t data[28] = {0};
        data[0] = 0x2A; data[1] = 0xFF;
        data[20] = 0x02;  // phaseIndex = 2
        data[21] = 0x01;  // frameStatus = 1 (normal)
        data[26] = 0x03;  // phaseCount = 3

        QByteArray header(reinterpret_cast<char*>(data), 28);
        ParsedFrameHeader parsed = ImageProtocolParsing::parseFrameHeader(header);
        REQUIRE(parsed.phaseIndex == 2);
    }
}

void test_parse_frame_status_values() {
    // Test frame_status = 0 (idle)
    {
        uint8_t data[28] = {0};
        data[0] = 0x2A; data[1] = 0xFF;
        data[20] = 0x01;
        data[21] = 0x00;  // frameStatus = 0 (idle)
        data[26] = 0x03;

        QByteArray header(reinterpret_cast<char*>(data), 28);
        ParsedFrameHeader parsed = ImageProtocolParsing::parseFrameHeader(header);
        REQUIRE(parsed.frameStatus == 0);
    }

    // Test frame_status = 1 (normal)
    {
        uint8_t data[28] = {0};
        data[0] = 0x2A; data[1] = 0xFF;
        data[20] = 0x01;
        data[21] = 0x01;  // frameStatus = 1 (normal)
        data[26] = 0x03;

        QByteArray header(reinterpret_cast<char*>(data), 28);
        ParsedFrameHeader parsed = ImageProtocolParsing::parseFrameHeader(header);
        REQUIRE(parsed.frameStatus == 1);
    }

    // Test frame_status = 2 (transition)
    {
        uint8_t data[28] = {0};
        data[0] = 0x2A; data[1] = 0xFF;
        data[20] = 0x01;
        data[21] = 0x02;  // frameStatus = 2 (transition)
        data[26] = 0x03;

        QByteArray header(reinterpret_cast<char*>(data), 28);
        ParsedFrameHeader parsed = ImageProtocolParsing::parseFrameHeader(header);
        REQUIRE(parsed.frameStatus == 2);
    }
}

void test_parse_legacy_16_byte_header_backward_compatibility() {
    // Build a legacy 16-byte frame header
    uint8_t data[16] = {0};

    // Magic: 0x2AFF (big endian at offset 0-1)
    data[0] = 0x2A;
    data[1] = 0xFF;

    // Frame counter: 0x0005 (big endian at offset 2-3)
    data[2] = 0x00;
    data[3] = 0x05;

    // Sample point: 500000 (0x0007A120, little endian at offset 4-7)
    data[4] = 0x20;
    data[5] = 0xA1;
    data[6] = 0x07;
    data[7] = 0x00;

    // Phase X: 10000000 (0x00989680, little endian at offset 8-11)
    data[8] = 0x80;
    data[9] = 0x96;
    data[10] = 0x98;
    data[11] = 0x00;

    // Phase Y: 20000000 (0x01312d00, little endian at offset 12-15)
    data[12] = 0x00;
    data[13] = 0x2D;
    data[14] = 0x31;
    data[15] = 0x01;

    QByteArray header(reinterpret_cast<char*>(data), 16);
    ParsedFrameHeader parsed = ImageProtocolParsing::parseFrameHeader(header);

    REQUIRE(parsed.valid == true);
    REQUIRE(parsed.frameId == 0x0005);
    REQUIRE(parsed.samplePoint == 500000);
    REQUIRE(parsed.phaseX == 10000000);
    REQUIRE(parsed.phaseY == 20000000);
    // Extended fields should remain at defaults (0)
    REQUIRE(parsed.phaseFrameId == 0);
    REQUIRE(parsed.phaseIndex == 0);
    REQUIRE(parsed.frameStatus == 0);
    REQUIRE(parsed.currentXInitialPhase == 0);
    REQUIRE(parsed.currentYInitialPhase == 0);
    REQUIRE(parsed.phaseCount == 0);
}

void test_parse_header_too_small() {
    // Test with less than 16 bytes
    uint8_t data[4] = {0x2A, 0xFF, 0x00, 0x01};
    QByteArray header(reinterpret_cast<char*>(data), 4);
    ParsedFrameHeader parsed = ImageProtocolParsing::parseFrameHeader(header);

    REQUIRE(parsed.valid == false);
}

void test_parse_exactly_16_bytes() {
    // Test with exactly 16 bytes (legacy boundary)
    uint8_t data[16] = {0};
    data[0] = 0x2A;
    data[1] = 0xFF;
    data[2] = 0x00;
    data[3] = 0x03;
    data[4] = 0x00;
    data[5] = 0x00;
    data[6] = 0x10;
    data[7] = 0x00;
    data[8] = 0x00;
    data[9] = 0x00;
    data[10] = 0x00;
    data[11] = 0x00;
    data[12] = 0x00;
    data[13] = 0x00;
    data[14] = 0x00;
    data[15] = 0x00;

    QByteArray header(reinterpret_cast<char*>(data), 16);
    ParsedFrameHeader parsed = ImageProtocolParsing::parseFrameHeader(header);

    REQUIRE(parsed.valid == true);
    REQUIRE(parsed.frameId == 3);
    REQUIRE(parsed.samplePoint == 1048576);
    // Extended fields should not be parsed
    REQUIRE(parsed.phaseIndex == 0);
    REQUIRE(parsed.frameStatus == 0);
}

}  // namespace

void runImageProtocolParsingTests() {
    test_parse_standard_28_byte_header();
    test_parse_phase_index_values();
    test_parse_frame_status_values();
    test_parse_legacy_16_byte_header_backward_compatibility();
    test_parse_header_too_small();
    test_parse_exactly_16_bytes();
}