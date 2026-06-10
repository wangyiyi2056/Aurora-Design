const axios = require('axios');
async function test() {
  try {
    const res = await axios.get('http://127.0.0.1:8888/v1/knowledge/test/graph/subgraph', {
      params: { label: '*', max_depth: 3, max_nodes: 1000 }
    });
    console.log(JSON.stringify(res.data, null, 2).substring(0, 500));
    console.log("Nodes length:", res.data.nodes?.length);
  } catch (e) {
    console.error(e.response ? e.response.status : e.message);
  }
}
test();
