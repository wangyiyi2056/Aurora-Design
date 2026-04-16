import { useQuery, useMutation } from "@tanstack/react-query"
import { listOperators, runAwel } from "@/services/flow"

export function useOperators() {
  return useQuery({
    queryKey: ["flow", "operators"],
    queryFn: listOperators,
  })
}

export function useRunAwel() {
  return useMutation({
    mutationFn: runAwel,
  })
}
