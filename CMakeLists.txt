if(CONFIG_CORNE_RGB_STATUS_SCREEN)
  target_sources(app PRIVATE ${CMAKE_CURRENT_LIST_DIR}/src/display/status_screen.c)
endif()
