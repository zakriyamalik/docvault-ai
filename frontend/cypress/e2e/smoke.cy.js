describe('Smoke Test', () => {
  it('app loads', () => {
    cy.visit('/');
    cy.contains('DocVault');
  });

  it('chat page loads', () => {
    cy.visit('/chat');
    cy.contains('How can I help you?');
  });
});