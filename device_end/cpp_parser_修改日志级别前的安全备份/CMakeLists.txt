cmake_minimum_required(VERSION 3.10)
project(cpp_parser)

# 设置策略以消除关于 FindBoost 的开发者警告
#cmake_policy(SET CMP0167 NEW)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 添加头文件搜索路径
include_directories(
    include
    external/include
    /usr/local/include
)

# 查找依赖库
find_package(Boost REQUIRED COMPONENTS system thread filesystem)
find_package(Threads REQUIRED)

# 优先使用系统 x86_64 架构的 OpenSSL
set(OPENSSL_ROOT_DIR "/usr/lib/x86_64-linux-gnu")
find_package(OpenSSL REQUIRED)

# 添加调试信息，确认找到的 OpenSSL 库路径
if(OPENSSL_FOUND)
    message(STATUS "  -> Found OpenSSL: ${OPENSSL_VERSION}")
    message(STATUS "     Libraries: ${OPENSSL_LIBRARIES}")
endif()

# --------- MySQL client ----------
find_library(MYSQLCLIENT_LIB mysqlclient)
if(NOT MYSQLCLIENT_LIB)
    message(FATAL_ERROR "mysqlclient library not found. Please install libmysqlclient-dev")
endif()

# 可选：使用内存版 Mock DB（单元测试）
option(USE_MOCK_DB "Build with in-memory mock database" OFF)

# Redis 实现选择
message(STATUS "Using redis++ and hiredis for Redis implementation")
add_definitions(-DUSE_SWREDIS)
set(REDIS_LIBRARIES redis++ hiredis)

# 添加源文件
file(GLOB_RECURSE SOURCES 
    "src/app/*.cpp"
    "src/logic/*.cpp"
    "src/logic/handlers/*.cpp"
    "src/logic/services/*.cpp"
    "src/logic/utils/*.cpp"
    "src/adapters/*.cpp"
)

# 如果未开启 USE_MOCK_DB，则从源列表排除 MockMySqlDatabaseAdaptor.cpp
if(NOT USE_MOCK_DB)
    list(FILTER SOURCES EXCLUDE REGEX ".*MockMySqlDatabaseAdaptor.cpp$")
endif()

# 创建可执行文件
add_executable(cpp_parser ${SOURCES})

# 链接库
target_link_libraries(cpp_parser
    PRIVATE
    Boost::system
    Boost::thread
    Boost::filesystem
    ${REDIS_LIBRARIES}
    Threads::Threads
    # 使用 ${OPENSSL_LIBRARIES} 变量进行链接，兼容性最好
    ${OPENSSL_LIBRARIES}
    ${MYSQLCLIENT_LIB}
)

# 设置编译选项
target_compile_options(cpp_parser PRIVATE -Wall -Wextra -O3)

# 设置输出目录
set_target_properties(cpp_parser PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
)

# 创建配置文件拷贝
configure_file(
    ${CMAKE_SOURCE_DIR}/config/parser_config.json
    ${CMAKE_BINARY_DIR}/bin/parser_config.json
    COPYONLY
)

# 创建协议文件拷贝
configure_file(
    ${CMAKE_SOURCE_DIR}/config/dp_protocol_v1.json
    ${CMAKE_BINARY_DIR}/bin/dp_protocol_v1.json
    COPYONLY
)

configure_file(
    ${CMAKE_SOURCE_DIR}/config/dp_protocol_v2.json
    ${CMAKE_BINARY_DIR}/bin/dp_protocol_v2.json
    COPYONLY
)

configure_file(
    ${CMAKE_SOURCE_DIR}/config/modbus_tcp.json
    ${CMAKE_BINARY_DIR}/bin/modbus_tcp.json
    COPYONLY
)

configure_file(
    ${CMAKE_SOURCE_DIR}/config/protocol_registry.json
    ${CMAKE_BINARY_DIR}/bin/protocol_registry.json
    COPYONLY
)

configure_file(
    ${CMAKE_SOURCE_DIR}/config/database_mapping.json
    ${CMAKE_BINARY_DIR}/bin/database_mapping.json
    COPYONLY
)

configure_file(
    ${CMAKE_SOURCE_DIR}/config/universal_parsing_rules.json
    ${CMAKE_BINARY_DIR}/bin/universal_parsing_rules.json
    COPYONLY
)

configure_file(
    ${CMAKE_SOURCE_DIR}/config/protocol_parsing_strategies.json
    ${CMAKE_BINARY_DIR}/bin/protocol_parsing_strategies.json
    COPYONLY
)

# 创建测试程序
add_executable(test_simple_parser test/test_simple_parser.cpp)

target_link_libraries(test_simple_parser
    PRIVATE
    ${REDIS_LIBRARIES}
    Threads::Threads
    ${OPENSSL_LIBRARIES}
    ${MYSQLCLIENT_LIB}
)

target_compile_options(test_simple_parser PRIVATE -Wall -Wextra -O3)

set_target_properties(test_simple_parser PROPERTIES
    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
)

# 通用解析器测试（暂时注释掉，等实现完成后再启用）
# add_executable(test_universal_parser test/test_universal_parser.cpp src/logic/UniversalParser.cpp src/logic/ResponseGenerator.cpp)

# target_link_libraries(test_universal_parser
#     PRIVATE
#     ${REDIS_LIBRARIES}
#     Threads::Threads
#     ${OPENSSL_LIBRARIES}
#     ${MYSQLCLIENT_LIB}
# )

# target_compile_options(test_universal_parser PRIVATE -Wall -Wextra -O3)

# set_target_properties(test_universal_parser PROPERTIES
#     RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
# )
