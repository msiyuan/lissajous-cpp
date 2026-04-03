add_rules("mode.debug", "mode.release")

-- 设置平台为 MinGW
set_plat("mingw")
set_arch("x86_64")

-- 设置 MinGW 工具链路径
set_config("mingw", "D:\\DevelopTool\\Qt6.3.1\\Tools\\mingw1310_64")

-- 设置 Qt SDK 路径
set_config("qt", "D:\\DevelopTool\\Qt6.3.1\\6.8.0\\mingw_64")

target("MEMS-Vision-Pro")
    add_rules("qt.widgetapp")

    -- 启用 C++17
    set_languages("c++17")

    -- 添加 Qt 模块
    add_frameworks("QtCore", "QtGui", "QtWidgets", "QtNetwork")

    -- 源文件
    add_files("src/*.cpp")
    add_files("src/config/*.h")
    add_files("src/network/*.cpp")
    add_files("src/processing/*.cpp")
    add_files("src/ui/*.cpp")
    add_files("src/utils/*.cpp")  -- 添加utils目录的cpp文件
    add_files("src/utils/*.h")

    -- 头文件目录
    add_includedirs("src")

    -- MOC 文件 (Qt 元对象)
    add_files("src/network/*.h")
    add_files("src/processing/*.h")
    add_files("src/ui/*.h")
