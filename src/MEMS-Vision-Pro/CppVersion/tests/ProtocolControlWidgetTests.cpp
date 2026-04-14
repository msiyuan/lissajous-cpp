#include "ui/ProtocolControlWidget.h"
#include "ui/ProtocolControlWorkflow.h"
#include "network/ProtocolCommands.h"
#include "TestSupport.h"

#include <QPushButton>

namespace {

void test_control_workflow_matches_requested_startup_and_shutdown_sequences() {
    const auto startup = ProtocolControlWorkflow::startupSequence();
    REQUIRE(startup.size() == 3);
    REQUIRE(startup[0].address == ProtocolCommands::REG_MEMS_EN);
    REQUIRE(startup[0].value == 1);
    REQUIRE(startup[1].address == ProtocolCommands::REG_MEMS_START);
    REQUIRE(startup[1].value == 1);
    REQUIRE(startup[2].address == ProtocolCommands::REG_LIVE);
    REQUIRE(startup[2].value == 1);

    const auto shutdown = ProtocolControlWorkflow::shutdownSequence();
    REQUIRE(shutdown.size() == 3);
    REQUIRE(shutdown[0].address == ProtocolCommands::REG_EXIT);
    REQUIRE(shutdown[0].value == 1);
    REQUIRE(shutdown[1].address == ProtocolCommands::REG_MEMS_START);
    REQUIRE(shutdown[1].value == 0);
    REQUIRE(shutdown[2].address == ProtocolCommands::REG_MEMS_EN);
    REQUIRE(shutdown[2].value == 0);
}

void test_control_widget_uses_explicit_action_buttons() {
    ProtocolControlWidget widget;

    const auto buttons = widget.findChildren<QPushButton*>();
    QStringList labels;
    for (QPushButton* button : buttons) {
        labels << button->text();
    }

    REQUIRE(labels.contains("执行启动流程"));
    REQUIRE(labels.contains("执行结束流程"));
    REQUIRE(labels.contains("使能MEMS"));
    REQUIRE(labels.contains("关闭MEMS"));
    REQUIRE(labels.contains("启动MEMS"));
    REQUIRE(labels.contains("停止MEMS"));
    REQUIRE(labels.contains("开始成像"));
    REQUIRE(labels.contains("结束成像"));

    REQUIRE(!labels.contains("正常工作"));
    REQUIRE(!labels.contains("扫频停止"));
    REQUIRE(!labels.contains("AD采集"));
}

}  // namespace

void runProtocolControlWidgetTests() {
    test_control_workflow_matches_requested_startup_and_shutdown_sequences();
    test_control_widget_uses_explicit_action_buttons();
}
