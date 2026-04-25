# Daily budget guards for external APIs.
# Each breaker reads its current spend from Supabase and raises BudgetExceeded
# when the daily limit is hit. Cohere falls back to no-rerank instead of erroring.
