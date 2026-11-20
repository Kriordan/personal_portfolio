import type { DraftStorage } from './practice-drafts.ts';
import { PracticeEditDrafts } from './practice-work-drafts.ts';
import {
  copyResponse,
  responseKey,
  validResponseEdit,
  type ResponseEdit,
} from './feedback-response-model.ts';

export const responseDraftIndex = 'learning.practice.responses.v1';
export class FeedbackResponseDrafts extends PracticeEditDrafts<ResponseEdit> {
  constructor(
    userId: number,
    storage: DraftStorage,
    serial: <T>(run: () => Promise<T>) => Promise<T>,
  ) {
    super(userId, storage, serial, {
      namespace: responseDraftIndex,
      label: 'Feedback response',
      limit: 50,
      valid: (edit): edit is ResponseEdit => validResponseEdit(edit, true),
      copy: copyResponse,
      key: responseKey,
      same: (a, b) =>
        JSON.stringify(copyResponse(a)) === JSON.stringify(copyResponse(b)),
    });
  }
}
