# CMakeLists.txt — helpers for build automation

# Post-build step to fix compile_commands.json paths for portability
add_custom_target(fix_compile_commands
    COMMAND ${CMAKE_COMMAND} -P ${CMAKE_CURRENT_LIST_DIR}/cmake/fix_compile_commands.cmake
    COMMENT "Fixing compile_commands.json paths for portability..."
    VERBATIM
)

# Make ALL targets depend on this post-build step
# (This ensures it runs after cmake --build, but doesn't block clean)
add_custom_target(post_build_hooks ALL DEPENDS fix_compile_commands)
