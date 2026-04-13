#include "config/Constants.h"
#include "network/ProtocolCommands.h"
#include "utils/PhaseMapping.h"
#include "TestSupport.h"
#include "ui/DualChannelSessionState.h"

namespace {

void test_default_ports_and_frequencies() {
    REQUIRE(Config::UDP_PORT_CH1 == 0x8001);
    REQUIRE(Config::UDP_PORT_CH2 == 0x8000);
    REQUIRE(Config::DEFAULT_FREQ_X == 11380.0);
    REQUIRE(Config::DEFAULT_FREQ_Y == 3760.0);
}

void test_start_stop_transitions() {
    DualChannelSessionState state;
    REQUIRE(!state.imagingActive());
    REQUIRE(!state.stackRecording());

    REQUIRE(state.startImaging());
    REQUIRE(state.imagingActive());
    REQUIRE(!state.startImaging());

    REQUIRE(state.startStackRecording());
    REQUIRE(state.stackRecording());

    const bool shouldFinalizeStacks = state.stopImaging();
    REQUIRE(shouldFinalizeStacks);
    REQUIRE(!state.imagingActive());
    REQUIRE(!state.stackRecording());
}

void test_stop_without_recording_does_not_request_stack_finalize() {
    DualChannelSessionState state;
    REQUIRE(state.startImaging());
    REQUIRE(!state.stackRecording());

    const bool shouldFinalizeStacks = state.stopImaging();
    REQUIRE(!shouldFinalizeStacks);
}

void test_explicit_stop_recording_clears_flag() {
    DualChannelSessionState state;
    REQUIRE(state.startStackRecording());
    REQUIRE(state.stackRecording());
    REQUIRE(state.stopStackRecording());
    REQUIRE(!state.stackRecording());
}

void test_stats_text_contains_both_channels() {
    DualChannelSessionState state;

    ChannelCounters ch1;
    ch1.bytes = 4096;
    ch1.packets = 12;
    ch1.frames = 3;

    ChannelCounters ch2;
    ch2.bytes = 8192;
    ch2.packets = 22;
    ch2.frames = 6;

    const QString text = state.buildStatsText(ch1, ch2, 9);
    REQUIRE(text.contains("CH1: 4 KB"));
    REQUIRE(text.contains("CH2: 8 KB"));
    REQUIRE(text.contains("3 帧"));
    REQUIRE(text.contains("6 帧"));
    REQUIRE(text.contains("FPS: 9"));
}

void test_paired_image_plan_uses_one_timestamp() {
    DualChannelSessionState state;
    const auto plan = state.buildImageSavePlan("saved_data", "20260413_101500", true, true);

    REQUIRE(plan.savedChannels.size() == 2);
    REQUIRE(plan.savedChannels[0] == "ch1");
    REQUIRE(plan.savedChannels[1] == "ch2");
    REQUIRE(plan.pathsByChannel.value("ch1").contains("20260413_101500"));
    REQUIRE(plan.pathsByChannel.value("ch2").contains("20260413_101500"));
}

void test_partial_image_plan_does_not_drop_available_channel() {
    DualChannelSessionState state;
    const auto plan = state.buildImageSavePlan("saved_data", "20260413_101500", true, false);

    REQUIRE(plan.savedChannels.size() == 1);
    REQUIRE(plan.savedChannels[0] == "ch1");
    REQUIRE(plan.missingChannels.size() == 1);
    REQUIRE(plan.missingChannels[0] == "ch2");
}

void test_paired_stack_plan_uses_one_timestamp() {
    DualChannelSessionState state;
    const auto plan = state.buildStackSavePlan("saved_data", "20260413_104500", true, true);

    REQUIRE(plan.savedChannels.size() == 2);
    REQUIRE(plan.pathsByChannel.value("ch1").contains("20260413_104500"));
    REQUIRE(plan.pathsByChannel.value("ch2").contains("20260413_104500"));
    REQUIRE(plan.pathsByChannel.value("ch1").contains("stack"));
    REQUIRE(plan.pathsByChannel.value("ch2").contains("stack"));
}

void test_protocol_control_registers_match_python_flow() {
    REQUIRE(ProtocolCommands::REG_MEMS_EN == 0x0114);
    REQUIRE(ProtocolCommands::REG_MEMS_START == 0x0115);
    REQUIRE(ProtocolCommands::REG_NORMAL_WORK_START == 0x0116);
    REQUIRE(ProtocolCommands::REG_SWEEP_STOP == 0x0117);
    REQUIRE(ProtocolCommands::REG_MANUAL_AD_SAMP == 0x0118);
}

void test_protocol_defaults_include_control_registers() {
    const auto defaults = ProtocolCommands::getDefaultValues();

    REQUIRE(defaults.contains(ProtocolCommands::REG_MEMS_EN));
    REQUIRE(defaults.contains(ProtocolCommands::REG_MEMS_START));
    REQUIRE(defaults.contains(ProtocolCommands::REG_NORMAL_WORK_START));
    REQUIRE(defaults.contains(ProtocolCommands::REG_SWEEP_STOP));
    REQUIRE(defaults.contains(ProtocolCommands::REG_MANUAL_AD_SAMP));
    REQUIRE(defaults.contains(ProtocolCommands::REG_SWEEP_REPEAT_NUM));
    REQUIRE(defaults.contains(ProtocolCommands::REG_X_PHASE_ADD_VALUE));
    REQUIRE(defaults.contains(ProtocolCommands::REG_Y_PHASE_ADD_VALUE));
    REQUIRE(defaults.contains(ProtocolCommands::REG_AD_SAMP_PERIOD));
    REQUIRE(defaults.contains(ProtocolCommands::REG_FF_INTERVAL_PERIOD));

    REQUIRE(defaults.value(ProtocolCommands::REG_MEMS_EN) == 0);
    REQUIRE(defaults.value(ProtocolCommands::REG_MEMS_START) == 0);
    REQUIRE(defaults.value(ProtocolCommands::REG_NORMAL_WORK_START) == 0);
    REQUIRE(defaults.value(ProtocolCommands::REG_SWEEP_STOP) == 0);
    REQUIRE(defaults.value(ProtocolCommands::REG_MANUAL_AD_SAMP) == 0);
    REQUIRE(defaults.value(ProtocolCommands::REG_SWEEP_REPEAT_NUM) == 1);
    REQUIRE(defaults.value(ProtocolCommands::REG_X_PHASE_ADD_VALUE) == 763698);
    REQUIRE(defaults.value(ProtocolCommands::REG_Y_PHASE_ADD_VALUE) == 252329);
    REQUIRE(defaults.value(ProtocolCommands::REG_AD_SAMP_PERIOD) == 12000000);
    REQUIRE(defaults.value(ProtocolCommands::REG_FF_INTERVAL_PERIOD) == 1200000);
}

void test_phase_mapping_constants_match_msycode() {
    REQUIRE(PhaseMapping::X_PHASE_COMPENSATION_LOW == 0.0);
    REQUIRE(PhaseMapping::X_PHASE_COMPENSATION_HIGH == 180.0);
    REQUIRE(PhaseMapping::Y_PHASE_COMPENSATION_LOW == 0.0);
    REQUIRE(PhaseMapping::Y_PHASE_COMPENSATION_HIGH == 180.0);
}

void test_phase_mapping_x_sequence_matches_msycode() {
    PhaseMapping mapping;

    REQUIRE(mapping.mapDeltaPhaseX(10.0) == 0.0);
    REQUIRE(mapping.mapDeltaPhaseX(20.0) == 180.0);
    REQUIRE(mapping.mapDeltaPhaseX(15.0) == 180.0);
    REQUIRE(mapping.mapDeltaPhaseX(30.0) == 0.0);
}

void test_phase_mapping_y_sequence_matches_msycode() {
    PhaseMapping mapping;

    REQUIRE(mapping.mapDeltaPhaseY(10.0) == 0.0);
    REQUIRE(mapping.mapDeltaPhaseY(20.0) == 180.0);
    REQUIRE(mapping.mapDeltaPhaseY(15.0) == 180.0);
    REQUIRE(mapping.mapDeltaPhaseY(30.0) == 0.0);
}

void test_phase_formula_matches_msycode() {
    REQUIRE(PhaseMapping::rawPhaseToMappingDegrees(16777216u) == 180.0);
    REQUIRE(PhaseMapping::rawPhaseToDisplayDegrees(16777216u) == 90.0);
    REQUIRE(PhaseMapping::composeFinalPhaseDegrees(16777216u, 180.0, 5.0) == 275.0);
}

}  // namespace

void runDualChannelSessionStateTests() {
    test_default_ports_and_frequencies();
    test_start_stop_transitions();
    test_stop_without_recording_does_not_request_stack_finalize();
    test_explicit_stop_recording_clears_flag();
    test_stats_text_contains_both_channels();
    test_paired_image_plan_uses_one_timestamp();
    test_partial_image_plan_does_not_drop_available_channel();
    test_paired_stack_plan_uses_one_timestamp();
    test_protocol_control_registers_match_python_flow();
    test_protocol_defaults_include_control_registers();
    test_phase_mapping_constants_match_msycode();
    test_phase_mapping_x_sequence_matches_msycode();
    test_phase_mapping_y_sequence_matches_msycode();
    test_phase_formula_matches_msycode();
}
