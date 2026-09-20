import { render, screen } from '@testing-library/react';
import { ProductSkeleton } from '../src/ui/ProductSkeleton';

test('announces loading to screen readers via a status role', () => {
  render(<ProductSkeleton />);
  expect(screen.getByRole('status')).toHaveTextContent('Loading product…');
});

test('the visual placeholder blocks are hidden from assistive tech', () => {
  const { container } = render(<ProductSkeleton />);
  const hidden = container.querySelectorAll('[aria-hidden="true"]');
  expect(hidden.length).toBeGreaterThan(0);
});
