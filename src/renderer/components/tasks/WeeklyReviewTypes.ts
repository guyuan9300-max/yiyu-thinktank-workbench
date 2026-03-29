export type EventLineGapActionPayload = {
  eventLineId: string;
  title: string;
  actionType: 'upload_docs' | 'clarify_now';
  slotLabels: string[];
};
