CC = g++ -std=c++20 -O3 -Wall -Wextra -o
TCC = g++ -std=c++20 -ggdb -Wall -Wextra -o
INC = src/road_network.cpp src/util.cpp

default: main
all: main index query topcut test hc2l_routing_api
main:
	$(CC) cut src/main.cpp $(INC)
index:
	$(CC) index src/index.cpp $(INC)
query:
	$(CC) query src/query.cpp $(INC)
topcut:
	$(CC) topcut src/topcut.cpp $(INC)
test:
	$(TCC) test src/test.cpp $(INC)
hc2l_routing_api:
	$(CC) hc2l_routing_api src/hc2l_routing_api.cpp $(INC)
clean:
	rm -f cut index query topcut test hc2l_routing_api

.PHONY: main index query topcut test hc2l_routing_api
