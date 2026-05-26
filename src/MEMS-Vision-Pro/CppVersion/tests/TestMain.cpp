#include <QApplication>
#include <QLibraryInfo>
#include <iostream>

void runDualChannelSessionStateTests();
void runDualChannelFpsTrackerTests();
void runDataSaverTests();
void runProtocolControlWidgetTests();
void runDisplayFrameFusionTests();
void runImageProtocolParsingTests();
void runFrameAssemblerTests();
void runMultiPhaseFrameBufferTests();
void runMultiPhaseFusionProcessorTests();

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    QCoreApplication::addLibraryPath(QLibraryInfo::path(QLibraryInfo::PluginsPath));
    runDualChannelSessionStateTests();
    runDualChannelFpsTrackerTests();
    runDataSaverTests();
    runProtocolControlWidgetTests();
    runDisplayFrameFusionTests();
    runImageProtocolParsingTests();
    runFrameAssemblerTests();
    runMultiPhaseFrameBufferTests();
    runMultiPhaseFusionProcessorTests();
    std::cout << "All cppversion tests passed" << std::endl;
    return 0;
}
