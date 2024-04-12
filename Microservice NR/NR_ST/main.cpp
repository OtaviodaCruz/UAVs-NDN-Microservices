#include <ndn-cxx/common.hpp>

#include "fib.h"
#include "named_router.h"
#include "log/logger.h"

static bool stop = false;
static void signal_handler(int signum) {
    stop = true;
}

int main(int argc, char *argv[]) {
    std::string name = "";
    uint16_t local_consumer_port = 0;
    uint16_t local_producer_port = 0;
    uint16_t local_command_port = 0;

    char flags = 0;
    for (int i = 1; i < argc; i += 2) {
        switch (argv[i][1]) {
            case 'n':
                name = argv[i + 1];
                flags |= 0x1;
                break;
            case 'c':
                local_consumer_port = std::atoi(argv[i + 1]);
                flags |= 0x2;
                break;
            case 'p':
                local_producer_port = std::atoi(argv[i + 1]);
                flags |= 0x4;
                break;
            case 'C':
                local_command_port = std::atoi(argv[i + 1]);
                flags |= 0x8;
                break;
            case 'h':
            default:
                exit(0);
                break;
        }
    }
    if (flags != 0xF) {
        exit(-1);
    }

    std::cout << "name router v1.0" << std::endl;

    logger::setFilename("logs.txt");
    logger::isTee(true);
    logger::setMinimalLogLevel(logger::INFO);

    NamedRouter nameRouter(name, local_consumer_port, local_producer_port, local_command_port);
    nameRouter.start();

    signal(SIGINT, signal_handler);
    signal(SIGTERM, signal_handler);

    do {
        sleep(15);
    }while(!stop);

    nameRouter.stop();

    return 0;
}