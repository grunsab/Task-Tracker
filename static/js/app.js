document.addEventListener('DOMContentLoaded', function() {
  const taskCards = document.querySelectorAll('.task-card');
  const columns = document.querySelectorAll('.list-group');

  taskCards.forEach(card => {
    card.addEventListener('dragstart', dragStart);
    card.addEventListener('dragend', dragEnd);
  });

  columns.forEach(column => {
    column.addEventListener('dragover', dragOver);
    column.addEventListener('dragenter', dragEnter);
    column.addEventListener('dragleave', dragLeave);
    column.addEventListener('drop', drop);
  });

  let draggedCard = null;

  function dragStart() {
    draggedCard = this;
    setTimeout(() => this.style.display = 'none', 0);
  }

  function dragEnd() {
    draggedCard.style.display = 'block';
    draggedCard = null;
  }

  function dragOver(e) {
    e.preventDefault();
  }

  function dragEnter(e) {
    e.preventDefault();
    this.style.backgroundColor = 'rgba(0, 0, 0, 0.2)';
  }

  function dragLeave() {
    this.style.backgroundColor = 'rgba(0, 0, 0, 0.1)';
  }

  async function drop() {
    console.log('Task dropped into column');
    
    this.append(draggedCard);
    this.style.backgroundColor = 'rgba(0, 0, 0, 0.1)';

    const taskId = draggedCard.getAttribute('data-task-id');
    let newStatus = this.getAttribute('data-status');
    if (!newStatus) {
      console.error('Data-status attribute not found on drop target. Ensure your HTML element has a data-status attribute with values: todo, in_progress, or done.');
      alert('Drop target is missing the data-status attribute.');
      return;
    }
    newStatus = newStatus.trim();
    console.log('New status:', newStatus);

    const response = await fetch(`/tasks/${taskId}/update_status`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ status: newStatus }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      console.error('Error updating task status:', errorData);
      alert('Failed to update task status: ' + (errorData.error || 'Unknown error'));
    } else {
      console.log('Task status updated successfully');
    }
  }
}); 