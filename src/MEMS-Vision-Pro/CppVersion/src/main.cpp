#include <QApplication>
#include "ui/MainWindow.h"

int main(int argc, char *argv[]) {
    QApplication app(argc, argv);

    // 设置应用程序信息
    QApplication::setApplicationName("MEMS-Vision-Pro");
    QApplication::setApplicationVersion("1.0.0");
    QApplication::setOrganizationName("MEMS-Vision");

    MainWindow window;
    window.show();

    return app.exec();
}
