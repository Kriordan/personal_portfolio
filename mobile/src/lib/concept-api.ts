import { apiRequest } from './api-client';
import { createConceptClient } from './concept-client';
export const conceptApi = createConceptClient(apiRequest);
