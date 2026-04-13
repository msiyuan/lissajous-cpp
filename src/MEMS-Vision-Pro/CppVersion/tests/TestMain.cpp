#include <QCoreApplication>
#include <iostream>

void runDualChannelSessionStateTests();

int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    runDualChannelSessionStateTests();
    std::cout << "All dual-channel session tests passed" << std::endl;
    return 0;
}
