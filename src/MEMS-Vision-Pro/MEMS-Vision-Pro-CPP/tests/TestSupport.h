#ifndef TEST_SUPPORT_H
#define TEST_SUPPORT_H

#include <stdexcept>
#include <string>

inline void requireTrue(bool condition, const char* expression, const char* file, int line) {
    if (!condition) {
        throw std::runtime_error(
            std::string(file) + ":" + std::to_string(line) + " requirement failed: " + expression);
    }
}

#define REQUIRE(expr) requireTrue((expr), #expr, __FILE__, __LINE__)

#endif  // TEST_SUPPORT_H
