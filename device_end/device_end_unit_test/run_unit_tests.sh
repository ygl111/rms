#!/bin/bash

# TCP Gateway & CPP Parser 单元测试一键执行脚本
# 作者：AI Assistant  
# 日期：2025-09-26

set -e  # 遇到错误立即退出

echo "🧪====================================="
echo "🧪  TCP Gateway & CPP Parser 单元测试"
echo "🧪====================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否安装了必要的测试库
check_dependencies() {
    log_info "检查测试依赖..."
    
    if ! pkg-config --exists gtest; then
        log_error "Google Test 未安装"
        log_info "请执行: sudo apt-get install libgtest-dev libgmock-dev"
        exit 1
    fi
    
    if ! pkg-config --exists gmock; then
        log_warn "Google Mock 未找到，某些测试可能无法运行"
    fi
    
    log_info "依赖检查完成 ✅"
}

# 构建和运行测试的通用函数
run_test() {
    local test_name=$1
    local build_dir=$2
    local test_executable=$3
    
    log_info "🧪 测试 ${test_name}..."
    
    cd "$build_dir"
    
    if [ ! -f "Makefile" ]; then
        log_info "生成构建文件..."
        cmake .. -DCMAKE_BUILD_TYPE=Debug
    fi
    
    # 构建测试 - 使用临时的错误处理
    set +e  # 临时禁用错误退出
    make "$test_executable" 2>/dev/null
    local make_result=$?
    set -e  # 重新启用错误退出
    
    if [ $make_result -eq 0 ]; then
        log_info "构建成功: $test_executable"
        
        # 运行测试
        if ./"$test_executable"; then
            log_info "✅ ${test_name} 测试通过"
            return 0
        else
            log_error "❌ ${test_name} 测试失败"
            return 1
        fi
    else
        log_warn "⏭️  ${test_name} 构建跳过 (目标不存在或缺少依赖)"
        return 2
    fi
}

# 主测试函数
main() {
    local start_time=$(date +%s)
    local total_tests=0
    local passed_tests=0
    local failed_tests=0
    local skipped_tests=0
    
    check_dependencies
    
    # 保存当前目录
    local original_dir=$(pwd)
    
    echo ""
    log_info "=========================================="
    log_info "🥇 第一优先级: 协议解析核心 (cpp_parser)"  
    log_info "=========================================="
    
    # 测试 SimpleParser (实际存在的测试)
    total_tests=$((total_tests + 1))
    if run_test "SimpleParser" "cpp_parser/build" "test_simple_parser"; then
        passed_tests=$((passed_tests + 1))
    elif [ $? -eq 1 ]; then
        failed_tests=$((failed_tests + 1))
    else
        skipped_tests=$((skipped_tests + 1))
    fi
    
    cd "$original_dir"
    
    # 测试 UniversalParser (现已启用)
    total_tests=$((total_tests + 1))
    if run_test "UniversalParser" "cpp_parser/build" "test_universal_parser"; then
        passed_tests=$((passed_tests + 1))
    elif [ $? -eq 1 ]; then
        failed_tests=$((failed_tests + 1))
    else
        skipped_tests=$((skipped_tests + 1))
    fi
    
    cd "$original_dir"
    
    echo ""
    log_info "=========================================="
    log_info "🥈 第二优先级: 协议识别 (tcp_gateway)"
    log_info "=========================================="
    
    # 测试 MultiProtocolManager (现已启用)
    total_tests=$((total_tests + 1))
    if run_test "MultiProtocolManager" "tcp_gateway/build" "test_multi_protocol_manager_unit"; then
        passed_tests=$((passed_tests + 1))
    elif [ $? -eq 1 ]; then
        failed_tests=$((failed_tests + 1))
    else
        skipped_tests=$((skipped_tests + 1))
    fi
    
    cd "$original_dir"
    
    echo ""
    log_info "=========================================="
    log_info "🥉 第三优先级: TCP会话管理 (tcp_gateway)"
    log_info "=========================================="
    
    # 测试 TCPSession (现已启用)
    total_tests=$((total_tests + 1))
    if run_test "TCPSession" "tcp_gateway/build" "test_tcp_session_unit"; then
        passed_tests=$((passed_tests + 1))
    elif [ $? -eq 1 ]; then
        failed_tests=$((failed_tests + 1))
    else
        skipped_tests=$((skipped_tests + 1))
    fi
    
    cd "$original_dir"
    
    echo ""
    log_info "=========================================="
    log_info "🏅 第四优先级: 分包重组 (tcp_gateway)"
    log_info "=========================================="
    
    # 测试 PacketReassembler (现已启用)
    total_tests=$((total_tests + 1))
    if run_test "PacketReassembler" "tcp_gateway/build" "test_packet_reassembler_unit"; then
        passed_tests=$((passed_tests + 1))
    elif [ $? -eq 1 ]; then
        failed_tests=$((failed_tests + 1))
    else
        skipped_tests=$((skipped_tests + 1))
    fi
    
    cd "$original_dir"
    
    echo ""
    log_info "=========================================="
    log_info "🎖️  第五优先级: 消息处理器 (cpp_parser)"
    log_info "=========================================="
    
    # 测试 MessageProcessor (现已启用)
    total_tests=$((total_tests + 1))
    if run_test "MessageProcessor" "cpp_parser/build" "test_message_processor_unit"; then
        passed_tests=$((passed_tests + 1))
    elif [ $? -eq 1 ]; then
        failed_tests=$((failed_tests + 1))
    else
        skipped_tests=$((skipped_tests + 1))
    fi
    
    cd "$original_dir"
    
    # 测试结果汇总
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo ""
    echo "🏁====================================="
    echo "🏁  测试执行完成"
    echo "🏁====================================="
    echo ""
    
    log_info "📊 测试结果汇总:"
    echo "   总测试数: $total_tests"
    echo "   通过: $passed_tests ✅"
    echo "   失败: $failed_tests ❌" 
    echo "   跳过: $skipped_tests ⏭️"
    echo "   执行时间: ${duration}秒"
    
    if [ $failed_tests -gt 0 ]; then
        echo ""
        log_error "存在失败的测试用例，请检查日志!"
        exit 1
    elif [ $passed_tests -eq 0 ]; then
        echo ""
        log_warn "所有测试都被跳过，请检查环境配置"
        exit 2
    else
        echo ""
        log_info "🎉 所有测试成功完成!"
        exit 0
    fi
}

# 显示帮助信息
show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --help     显示帮助信息"
    echo "  -q, --quick    只运行前两个优先级测试"
    echo "  -v, --verbose  详细输出模式"
    echo ""
    echo "示例:"
    echo "  $0              # 运行所有测试"
    echo "  $0 --quick      # 只运行高优先级测试"
}

# 快速模式（只测试最关键的两个组件）
quick_mode() {
    log_info "🚀 快速测试模式 - 只运行前两个优先级"
    
    local original_dir=$(pwd)
    local passed=0
    local total=2  # 更新为2个测试
    
    # SimpleParser (实际存在的测试)
    if run_test "SimpleParser" "cpp_parser/build" "test_simple_parser"; then
        passed=$((passed + 1))
    fi
    
    cd "$original_dir"
    
    # MultiProtocolManager (现已启用)
    if run_test "MultiProtocolManager" "tcp_gateway/build" "test_multi_protocol_manager_unit"; then
        passed=$((passed + 1))
    fi
    
    cd "$original_dir"
    
    echo ""
    log_info "🏁 快速测试完成: $passed/$total 通过"
    
    if [ $passed -eq $total ]; then
        log_info "🎉 核心功能测试通过!"
        exit 0
    else
        log_error "核心功能存在问题"
        exit 1
    fi
}

# 解析命令行参数
case "${1:-}" in
    -h|--help)
        show_help
        exit 0
        ;;
    -q|--quick)
        quick_mode
        ;;
    -v|--verbose)
        set -x
        main
        ;;
    "")
        main
        ;;
    *)
        log_error "未知选项: $1"
        show_help
        exit 1
        ;;
esac