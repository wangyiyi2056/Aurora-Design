import { useQuery } from "@tanstack/react-query"
import { listSkills } from "@/services/models"

export function useSkills() {
  return useQuery({
    queryKey: ["skills", "list"],
    queryFn: listSkills,
  })
}
