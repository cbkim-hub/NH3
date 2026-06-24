export type ID = string;

export type ApiError = {
  code: string;
  message: string;
  details?: Record<string, unknown>;
};

export type ApiResponse<T> = {
  data: T;
  meta?: Record<string, unknown>;
  error: ApiError | null;
};

export type Paginated<T> = {
  items: T[];
  total: number;
  page: number;
  size: number;
};
