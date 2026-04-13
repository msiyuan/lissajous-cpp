#include <QApplication>
#include <QLibraryInfo>
#include <iostream>

void runDualChannelSessionStateTests();
void runDataSaverTests();

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    QCoreApplication::addLibraryPath(QLibraryInfo::path(QLibraryInfo::PluginsPath));
    runDualChannelSessionStateTests();
    runDataSaverTests();
    std::cout << "All cppversion tests passed" << std::endl;
    return 0;
}
