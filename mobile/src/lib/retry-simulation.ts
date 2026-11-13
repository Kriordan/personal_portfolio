export type FailurePoint = 'after' | 'before' | 'success';
export function retrySteps(failure: FailurePoint, reuse: boolean) {
  const committed = failure !== 'before';
  return [
    { text: 'Client sends the order with key A.', orders: 0 },
    committed
      ? {
          text: 'The database commits one order and its receipt together.',
          orders: 1,
        }
      : {
          text: 'The service crashes before commit. The database rolls back the order and receipt.',
          orders: 0,
        },
    failure === 'success'
      ? {
          text: 'Success arrives. The client knows the order exists; no retry is needed.',
          orders: 1,
        }
      : {
          text: 'The client times out. The timeout alone cannot tell it whether the order committed.',
          orders: committed ? 1 : 0,
        },
    {
      text: reuse
        ? 'The client retries the same operation with key A.'
        : 'The client resends with a new key B, identifying a new operation.',
      orders: committed ? 1 : 0,
    },
    committed && reuse
      ? {
          text: 'Return the recorded result for A. No second order is created.',
          orders: 1,
        }
      : {
          text: 'Create an order and receipt for this key, then return success.',
          orders: committed ? 2 : 1,
        },
  ];
}
