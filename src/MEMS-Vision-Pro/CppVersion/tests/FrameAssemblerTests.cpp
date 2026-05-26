#include "processing/FrameAssembler.h"
#include "processing/ImageProtocolParsing.h"
#include "TestSupport.h"
#include <QByteArray>
#include <memory>

namespace {

void test_frame_data_carries_phase_metadata() {
    // Create a minimal frame header with phase metadata
    uint8_t headerData[28] = {0};

    // Magic: 0x2AFF
    headerData[0] = 0x2A;
    headerData[1] = 0xFF;

    // Frame counter: 0x0002
    headerData[2] = 0x00;
    headerData[3] = 0x02;

    // Sample point: 500000
    headerData[4] = 0x00;
    headerData[5] = 0xA1;
    headerData[6] = 0x07;
    headerData[7] = 0x00;

    // Phase X: 0
    headerData[8] = 0x00;
    headerData[9] = 0x00;
    headerData[10] = 0x00;
    headerData[11] = 0x00;

    // Phase Y: 45000000 (0x02AEA540)
    headerData[12] = 0x40;
    headerData[13] = 0xA5;
    headerData[14] = 0xAE;
    headerData[15] = 0x02;

    // Phase frame ID: 50 (0x00000032)
    headerData[16] = 0x32;
    headerData[17] = 0x00;
    headerData[18] = 0x00;
    headerData[19] = 0x00;

    // Phase index: 1
    headerData[20] = 0x01;

    // Frame status: 1 (normal)
    headerData[21] = 0x01;

    // Current X initial phase: 0
    headerData[22] = 0x00;
    headerData[23] = 0x00;

    // Current Y initial phase: 4500 (0x1194)
    headerData[24] = 0x94;
    headerData[25] = 0x11;

    // Phase count: 3
    headerData[26] = 0x03;

    // Fixed zero
    headerData[27] = 0x00;

    QByteArray header(reinterpret_cast<char*>(headerData), 28);

    // Parse header directly
    ParsedFrameHeader parsed = ImageProtocolParsing::parseFrameHeader(header);
    REQUIRE(parsed.valid == true);
    REQUIRE(parsed.frameId == 0x0002);
    REQUIRE(parsed.phaseFrameId == 50);
    REQUIRE(parsed.phaseIndex == 1);
    REQUIRE(parsed.frameStatus == 1);
}

void test_frame_data_phase_index_values() {
    // Test that FrameData can store phaseIndex = 0, 1, 2

    // Create a simple FrameData structure and verify it can store all phase indices
    auto frame = std::make_shared<FrameData>();

    // Test phaseIndex = 0
    frame->phaseIndex = 0;
    frame->frameStatus = 1;
    REQUIRE(frame->phaseIndex == 0);

    // Test phaseIndex = 1
    frame->phaseIndex = 1;
    REQUIRE(frame->phaseIndex == 1);

    // Test phaseIndex = 2
    frame->phaseIndex = 2;
    REQUIRE(frame->phaseIndex == 2);
}

void test_frame_data_frame_status_values() {
    // Test that FrameData can store all frame status values
    auto frame = std::make_shared<FrameData>();

    // Test idle (0)
    frame->frameStatus = 0;
    REQUIRE(frame->frameStatus == 0);

    // Test normal (1)
    frame->frameStatus = 1;
    REQUIRE(frame->frameStatus == 1);

    // Test transition (2)
    frame->frameStatus = 2;
    REQUIRE(frame->frameStatus == 2);
}

void test_frame_data_default_values() {
    // Test that FrameData default values are correct
    auto frame = std::make_shared<FrameData>();

    REQUIRE(frame->phaseFrameId == 0);
    REQUIRE(frame->phaseIndex == 0);
    REQUIRE(frame->frameStatus == 0);
}

}  // namespace

void runFrameAssemblerTests() {
    test_frame_data_carries_phase_metadata();
    test_frame_data_phase_index_values();
    test_frame_data_frame_status_values();
    test_frame_data_default_values();
}