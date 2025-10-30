CC = g++ -std=c++2a -O3 -Wall -Wextra -pthread -o
TCC = g++ -std=c++2a -ggdb -Wall -Wextra -o
INC = src/road_network.cpp src/util.cpp

all: index query update dhl_routing_api

index:
	$(CC) index src/index.cpp $(INC)
query:
	$(CC) query src/query.cpp $(INC)
update:
	$(CC) update src/update.cpp $(INC)
dhl_routing_api:
	$(CC) dhl_routing_api src/dhl_routing_api.cpp $(INC)

clean:
	rm -f index query update dhl_routing_api

.PHONY: index query update dhl_routing_api
