const cookies = jest.fn(() =>
  Promise.resolve({
    get: jest.fn(),
    set: jest.fn(),
    delete: jest.fn(),
  })
);

module.exports = { cookies };
