#include "road_network.h"
#include "util.h"

#include <iostream>
#include <fstream>

using namespace std;
using namespace road_network;

int main(int argc, char** argv)
{

    // read index
    ifstream ifs(string(argv[1]) + string("_hcl"));
    ContractionIndex con_index(ifs);
    ifs.close();

    vector<pair<NodeID, NodeID> > queries; NodeID a, b;

    // read query pairs
    ifs.open(argv[2]);
    while(ifs >> a >> b)
        queries.push_back(make_pair(a, b));
    ifs.close();

    // run queries
    for (pair<NodeID, NodeID> q : queries)
        cout << con_index.get_distance(q.first, q.second) << endl;


    return 0;
}
