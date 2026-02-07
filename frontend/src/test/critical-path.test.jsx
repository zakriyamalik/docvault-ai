import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import { MessageBubble } from '../components/chat/MessageBubble';
import { Button } from '../components/ui/Button';


// Mock scrollIntoView for jsdom
window.HTMLElement.prototype.scrollIntoView = vi.fn();
console.log('MessageBubble is ->', MessageBubble);
console.log('Button is ->', Button);

// Simple store for UI tests
function createTestStore() {
  return configureStore({
    reducer: {
      chat: (state = { messages: [], isLoading: false }) => state,
    },
  });
}

function renderWithProvider(ui) {
  return render(
    <Provider store={createTestStore()}>
      {ui}
    </Provider>
  );
}

describe('Critical Path', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders user message correctly', () => {
    const message = {
      message_id: 'msg-1',
      role: 'user',
      content: 'Hello world',
      timestamp: new Date().toISOString(),
      sources: [],
    };

    renderWithProvider(<MessageBubble message={message} />);
    
    expect(screen.getByText('You')).toBeInTheDocument();
    expect(screen.getByText('Hello world')).toBeInTheDocument();
  });

  it('renders assistant message with sources', () => {
    const message = {
      message_id: 'msg-2',
      role: 'assistant',
      content: 'Here is the answer',
      timestamp: new Date().toISOString(),
      sources: [
        {
          chunk_id: 'chunk-1',
          document_id: 'doc-1',
          chunk_index: 5,
          preview: 'Test preview',
          score: 0.95,
        },
      ],
    };

    renderWithProvider(<MessageBubble message={message} />);
    
    expect(screen.getByText('Assistant')).toBeInTheDocument();
    expect(screen.getByText('Here is the answer')).toBeInTheDocument();
    expect(screen.getByText(/source 1/i)).toBeInTheDocument();
    expect(screen.getByText('95%')).toBeInTheDocument();
  });

  it('button click works', async () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click me</Button>);
    
    await screen.getByText('Click me').click();
    expect(handleClick).toHaveBeenCalled();
  });
});