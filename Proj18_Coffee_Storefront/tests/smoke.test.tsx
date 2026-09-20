import { render, screen } from '@testing-library/react';
import App from '../src/App';

test('the app renders the store name', () => {
  render(<App />);
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Lantern Roasters');
});
