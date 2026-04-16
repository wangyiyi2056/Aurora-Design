import axios from "axios"

export async function testModelConnection(baseUrl: string, apiKey: string) {
  await axios.get(`${baseUrl}/models`, {
    timeout: 10000,
    headers: {
      Authorization: `Bearer ${apiKey}`,
    },
  })
}
