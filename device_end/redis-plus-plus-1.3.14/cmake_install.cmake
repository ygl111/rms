# Install script for directory: /home/rsb/rms/device_end/redis-plus-plus-1.3.14

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "/usr/local")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "Release")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Install shared libraries without execute permission?
if(NOT DEFINED CMAKE_INSTALL_SO_NO_EXE)
  set(CMAKE_INSTALL_SO_NO_EXE "1")
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "FALSE")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib" TYPE STATIC_LIBRARY FILES "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/libredis++.a")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  foreach(file
      "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libredis++.so.1.3.14"
      "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libredis++.so.1"
      )
    if(EXISTS "${file}" AND
       NOT IS_SYMLINK "${file}")
      file(RPATH_CHECK
           FILE "${file}"
           RPATH "")
    endif()
  endforeach()
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib" TYPE SHARED_LIBRARY FILES
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/libredis++.so.1.3.14"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/libredis++.so.1"
    )
  foreach(file
      "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libredis++.so.1.3.14"
      "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libredis++.so.1"
      )
    if(EXISTS "${file}" AND
       NOT IS_SYMLINK "${file}")
      if(CMAKE_INSTALL_DO_STRIP)
        execute_process(COMMAND "/usr/bin/strip" "${file}")
      endif()
    endif()
  endforeach()
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  if(EXISTS "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libredis++.so" AND
     NOT IS_SYMLINK "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libredis++.so")
    file(RPATH_CHECK
         FILE "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libredis++.so"
         RPATH "")
  endif()
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib" TYPE SHARED_LIBRARY FILES "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/libredis++.so")
  if(EXISTS "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libredis++.so" AND
     NOT IS_SYMLINK "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libredis++.so")
    if(CMAKE_INSTALL_DO_STRIP)
      execute_process(COMMAND "/usr/bin/strip" "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/libredis++.so")
    endif()
  endif()
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  if(EXISTS "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/share/cmake/redis++/redis++-targets.cmake")
    file(DIFFERENT EXPORT_FILE_CHANGED FILES
         "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/share/cmake/redis++/redis++-targets.cmake"
         "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/CMakeFiles/Export/share/cmake/redis++/redis++-targets.cmake")
    if(EXPORT_FILE_CHANGED)
      file(GLOB OLD_CONFIG_FILES "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/share/cmake/redis++/redis++-targets-*.cmake")
      if(OLD_CONFIG_FILES)
        message(STATUS "Old export file \"$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/share/cmake/redis++/redis++-targets.cmake\" will be replaced.  Removing files [${OLD_CONFIG_FILES}].")
        file(REMOVE ${OLD_CONFIG_FILES})
      endif()
    endif()
  endif()
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/cmake/redis++" TYPE FILE FILES "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/CMakeFiles/Export/share/cmake/redis++/redis++-targets.cmake")
  if("${CMAKE_INSTALL_CONFIG_NAME}" MATCHES "^([Rr][Ee][Ll][Ee][Aa][Ss][Ee])$")
    file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/cmake/redis++" TYPE FILE FILES "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/CMakeFiles/Export/share/cmake/redis++/redis++-targets-release.cmake")
  endif()
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/include/sw/redis++" TYPE FILE FILES
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/cmd_formatter.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/command.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/command_args.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/command_options.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/connection.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/connection_pool.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/cxx17/sw/redis++/cxx_utils.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/errors.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/hiredis_features.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/no_tls/sw/redis++/tls.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/pipeline.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/queued_redis.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/queued_redis.hpp"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/redis++.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/redis.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/redis.hpp"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/redis_cluster.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/redis_cluster.hpp"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/redis_uri.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/reply.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/sentinel.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/shards.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/shards_pool.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/subscriber.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/transaction.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/utils.h"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/version.h"
    )
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/include/sw/redis++/patterns" TYPE FILE FILES "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/src/sw/redis++/patterns/redlock.h")
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/share/cmake/redis++" TYPE FILE FILES
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/cmake/redis++-config.cmake"
    "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/cmake/redis++-config-version.cmake"
    )
endif()

if("x${CMAKE_INSTALL_COMPONENT}x" STREQUAL "xUnspecifiedx" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/pkgconfig" TYPE FILE FILES "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/cmake/redis++.pc")
endif()

if(NOT CMAKE_INSTALL_LOCAL_ONLY)
  # Include the install script for each subdirectory.
  include("/home/rsb/rms/device_end/redis-plus-plus-1.3.14/test/cmake_install.cmake")

endif()

if(CMAKE_INSTALL_COMPONENT)
  set(CMAKE_INSTALL_MANIFEST "install_manifest_${CMAKE_INSTALL_COMPONENT}.txt")
else()
  set(CMAKE_INSTALL_MANIFEST "install_manifest.txt")
endif()

string(REPLACE ";" "\n" CMAKE_INSTALL_MANIFEST_CONTENT
       "${CMAKE_INSTALL_MANIFEST_FILES}")
file(WRITE "/home/rsb/rms/device_end/redis-plus-plus-1.3.14/${CMAKE_INSTALL_MANIFEST}"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")
