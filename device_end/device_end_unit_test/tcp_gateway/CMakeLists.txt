# 设定CMake所需的最低版本
cmake_minimum_required(VERSION 3.10)

# -----------------------------------------------------------------------------
# 1. 项目基本设置
# -----------------------------------------------------------------------------
#cmake_policy(SET CMP0167 NEW)
project(tcp_gateway)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# -----------------------------------------------------------------------------
# 2. 添加头文件搜索路径
# -----------------------------------------------------------------------------
# 让CMake知道去哪里寻找我们自己的头文件 (.h) 和第三方头文件
include_directories(
    include             # 项目内部的头文件目录
    external/include    # 用于存放 nlohmann/json.hpp
    /usr/local/include  # 为redis-plus-plus和hiredis添加头文件路径
)

# -----------------------------------------------------------------------------
# 3. 查找需要编译链接的Boost库 和 线程库
# -----------------------------------------------------------------------------
# Boost的查找保持不变
find_package(Boost 1.71.0 REQUIRED COMPONENTS system thread)
if(Boost_FOUND)
    message(STATUS "  -> Found Boost: ${Boost_VERSION_STRING} at ${Boost_INCLUDE_DIRS}")
endif()

#查找线程库
find_package(Threads REQUIRED)
if(Threads_FOUND)
    message(STATUS "  -> Found Threads library.")
endif()


# -----------------------------------------------------------------------------
# 4. 指定库文件搜索路径
# -----------------------------------------------------------------------------
# 由于redis-plus-plus没有安装CMake配置文件，我们直接告诉链接器去哪里找 .a 或 .so 文件。
link_directories(/usr/local/lib)

# -----------------------------------------------------------------------------
# 5. 定义要生成的可执行文件
# -----------------------------------------------------------------------------
# 此部分保持不变
set(SOURCES
    src/app/main.cpp
    src/logic/Config.cpp
    src/logic/SessionManager.cpp
    src/logic/TCPServer.cpp
    src/logic/TCPSession.cpp
    src/logic/ProtocolIdentifier.cpp
    src/logic/MultiProtocolManager.cpp
    src/logic/PacketReassembler.cpp
    src/adapters/BoostNetAdaptors.cpp
    src/adapters/RedisSwAdaptors.cpp
    src/adapters/BoostBase64Adaptors.cpp)

# 生成可执行文件
add_executable(gateway ${SOURCES})

# -----------------------------------------------------------------------------
# 6. 链接依赖库到可执行文件
# -----------------------------------------------------------------------------
# Threads::Threads 已经在这里，所以这部分是正确的
target_link_libraries(gateway
    PRIVATE
    Boost::system
    Boost::thread
    redis++
    hiredis
    Threads::Threads  # 链接线程库
)

# Include directories
target_include_directories(gateway PRIVATE include)

# -----------------------------------------------------------------------------
# 7. 测试目标定义
# -----------------------------------------------------------------------------

# 查找Google Test库（可选）
find_package(PkgConfig QUIET)
if(PkgConfig_FOUND)
    pkg_check_modules(GTEST QUIET gtest)
    pkg_check_modules(GMOCK QUIET gmock)
endif()

# 如果找到了Google Test，则构建测试
if(GTEST_FOUND AND GMOCK_FOUND)
    message(STATUS "  -> Found Google Test, building unit tests")
    
    # MultiProtocolManager 单元测试
    add_executable(test_multi_protocol_manager_unit
        test/test_multi_protocol_manager_unit.cpp
        src/logic/MultiProtocolManager.cpp
        src/logic/Config.cpp
    )
    
    target_link_libraries(test_multi_protocol_manager_unit
        PRIVATE
        Boost::system
        Boost::thread
        ${GTEST_LIBRARIES}
        ${GMOCK_LIBRARIES}
        Threads::Threads
    )
    
    target_compile_options(test_multi_protocol_manager_unit PRIVATE ${GTEST_CFLAGS_OTHER})
    target_include_directories(test_multi_protocol_manager_unit PRIVATE ${GTEST_INCLUDE_DIRS} ${GMOCK_INCLUDE_DIRS})
    
    # TCPSession 单元测试  
    add_executable(test_tcp_session_unit
        test/test_tcp_session_unit.cpp
        src/logic/TCPSession.cpp
        src/logic/SessionManager.cpp
    )
    
    target_link_libraries(test_tcp_session_unit
        PRIVATE
        Boost::system
        Boost::thread
        ${GTEST_LIBRARIES}
        ${GMOCK_LIBRARIES}
        Threads::Threads
    )
    
    target_compile_options(test_tcp_session_unit PRIVATE ${GTEST_CFLAGS_OTHER})
    target_include_directories(test_tcp_session_unit PRIVATE ${GTEST_INCLUDE_DIRS} ${GMOCK_INCLUDE_DIRS})
    
    # PacketReassembler 单元测试
    add_executable(test_packet_reassembler_unit
        test/test_packet_reassembler_unit.cpp
        src/logic/PacketReassembler.cpp
    )
    
    target_link_libraries(test_packet_reassembler_unit
        PRIVATE
        Boost::system
        Boost::thread
        ${GTEST_LIBRARIES}
        ${GMOCK_LIBRARIES}
        Threads::Threads
    )
    
    target_compile_options(test_packet_reassembler_unit PRIVATE ${GTEST_CFLAGS_OTHER})
    target_include_directories(test_packet_reassembler_unit PRIVATE ${GTEST_INCLUDE_DIRS} ${GMOCK_INCLUDE_DIRS})
    
    # 设置测试可执行文件输出目录
    set_target_properties(test_multi_protocol_manager_unit test_tcp_session_unit test_packet_reassembler_unit
        PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin
    )
else()
    message(WARNING "  -> Google Test not found, unit tests will not be built")
    message(STATUS "     To install: sudo apt-get install libgtest-dev libgmock-dev")
endif()
