import axios from 'axios';

jest.mock('axios', () => ({ get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn() }));

test('CRUD and summary calls use the deployable same-origin API', () => {
  delete process.env.REACT_APP_API_BASE_URL;
  let todoService;
  jest.isolateModules(() => { todoService = require('./todoService').default; });
  todoService.getAllTodos();
  todoService.createTodo({ title: 'test' });
  todoService.updateTodo(7, { completed: true });
  todoService.deleteTodo(7);
  todoService.summarizeTodos();
  expect(axios.get).toHaveBeenCalledWith('/api/todos');
  expect(axios.post).toHaveBeenCalledWith('/api/todos', { title: 'test' });
  expect(axios.put).toHaveBeenCalledWith('/api/todos/7', { completed: true });
  expect(axios.delete).toHaveBeenCalledWith('/api/todos/7');
  expect(axios.post).toHaveBeenCalledWith('/api/todos/summarize');
});

test('native development can override the API at build time', () => {
  process.env.REACT_APP_API_BASE_URL = 'http://localhost:8080/api/todos';
  let todoService;
  jest.isolateModules(() => { todoService = require('./todoService').default; });
  todoService.getAllTodos();
  expect(axios.get).toHaveBeenCalledWith('http://localhost:8080/api/todos');
  delete process.env.REACT_APP_API_BASE_URL;
});
