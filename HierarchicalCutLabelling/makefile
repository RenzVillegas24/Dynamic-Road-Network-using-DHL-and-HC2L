CC = g++
CXXFLAGS = -std=c++20 -O3 -Wall -Wextra
DBGCC = g++
DBGFLAGS = -std=c++20 -ggdb -Wall -Wextra
INC = src/road_network.cpp src/util.cpp

# Output build directory (relative to this package)
BUILD_DIR = ../Main/build
BIN_DIR = $(BUILD_DIR)/hc2l

.PHONY: all index hc2l_routing_api clean

# Only build the artifacts used by setup.sh
all: $(BIN_DIR)/index $(BIN_DIR)/hc2l_routing_api

$(BIN_DIR):
	@mkdir -p $(BIN_DIR)

$(BIN_DIR)/index: | $(BIN_DIR)
	$(CC) $(CXXFLAGS) -o $@ src/index.cpp $(INC)

$(BIN_DIR)/hc2l_routing_api: | $(BIN_DIR)
	$(CC) $(CXXFLAGS) -o $@ src/hc2l_routing_api.cpp $(INC)

clean:
	rm -f $(BIN_DIR)/index $(BIN_DIR)/hc2l_routing_api

