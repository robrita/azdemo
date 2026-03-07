import { useQuery } from "@tanstack/react-query";
import { fetchItems, type PaginatedResponse, type Item } from "../services/api";

/**
 * Example hook wrapping TanStack Query for paginated items.
 * Pattern: one hook per data entity, encapsulate query key + fn.
 */
export function useItems(page = 1, pageSize = 20) {
  return useQuery<PaginatedResponse<Item>>({
    queryKey: ["items", page, pageSize],
    queryFn: () => fetchItems(page, pageSize),
  });
}
