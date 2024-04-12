#include "logger.h"

void logger::setFilename(const std::string &filename) {
    std::lock_guard<std::mutex> lock(mutex);
    file.open(filename);
    if (!file) {
        std::cerr << "logger can't open this file" << std::endl;
    }
}

void logger::isTee(bool state) {
    is_tee = state;
};

void logger::setMinimalLogLevel(Level l) {
    level = l;
}

void logger::log(Level l, const std::string &message) {
    static const std::vector<std::string> LEVEL_OUTPUT_STRINGS = {"[INFO] ", "[WARNING] ", "[ERROR] "};
    std::lock_guard<std::mutex> lock(mutex);
    if (l >= level) {
        if (file) {
            file << LEVEL_OUTPUT_STRINGS[l] << message << std::endl;
        }
        if (is_tee) {
            std::cout << LEVEL_OUTPUT_STRINGS[l] << message << std::endl;
        }
    }
}