class NotesManager {
    constructor() {
        this.notes = this.loadNotes();
        this.currentNoteId = null;
        this.sortOrder = 'newest'; // 'newest' или 'oldest'

        this.initializeEventListeners();
        this.renderNotes();
    }

    // Загрузка заметок из localStorage
    loadNotes() {
        const notes = localStorage.getItem('notes');
        return notes ? JSON.parse(notes) : [];
    }

    // Сохранение заметок в localStorage
    saveNotes() {
        localStorage.setItem('notes', JSON.stringify(this.notes));
    }

    // Инициализация обработчиков событий
    initializeEventListeners() {
        document.getElementById('addNoteBtn').addEventListener('click', () => {
            this.openModal();
        });

        document.getElementById('sortNewest').addEventListener('click', () => {
            this.sortOrder = 'newest';
            this.renderNotes();
        });

        document.getElementById('sortOldest').addEventListener('click', () => {
            this.sortOrder = 'oldest';
            this.renderNotes();
        });

        document.getElementById('tagFilter').addEventListener('input', () => {
            this.renderNotes();
        });

        document.getElementById('clearFilter').addEventListener('click', () => {
            document.getElementById('tagFilter').value = '';
            this.renderNotes();
        });

        document.getElementById('noteForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveNote();
        });

        document.getElementById('cancelBtn').addEventListener('click', () => {
            this.closeModal();
        });

        document.getElementById('noteModal').addEventListener('click', (e) => {
            if (e.target.id === 'noteModal') {
                this.closeModal();
            }
        });
    }

    // Открытие модального окна
    openModal(noteId = null) {
        this.currentNoteId = noteId;
        const modal = document.getElementById('noteModal');
        const modalTitle = document.getElementById('modalTitle');

        if (noteId) {
            modalTitle.textContent = 'Редактировать заметку';
            const note = this.notes.find(n => n.id === noteId);
            document.getElementById('noteTitle').value = note.title || '';
            document.getElementById('noteContent').value = note.content || '';
            document.getElementById('noteTags').value = note.tags ? note.tags.join(', ') : '';
            document.getElementById('notePinned').checked = note.pinned || false;
        } else {
            modalTitle.textContent = 'Новая заметка';
            document.getElementById('noteTitle').value = '';
            document.getElementById('noteContent').value = '';
            document.getElementById('noteTags').value = '';
            document.getElementById('notePinned').checked = false;
        }

        modal.style.display = 'flex';
    }

    // Закрытие модального окна
    closeModal() {
        document.getElementById('noteModal').style.display = 'none';
        this.currentNoteId = null;
    }

    // Сохранение заметки
    saveNote() {
        const title = document.getElementById('noteTitle').value.trim();
        const content = document.getElementById('noteContent').value.trim();
        const tagsInput = document.getElementById('noteTags').value.trim();
        const isPinned = document.getElementById('notePinned').checked;

        if (!title || !content) {
            alert('Пожалуйста, заполните заголовок и содержание.');
            return;
        }

        const tags = tagsInput
            ? tagsInput.split(',').map(t => t.trim()).filter(t => t)
            : [];

        if (this.currentNoteId) {
            const index = this.notes.findIndex(n => n.id === this.currentNoteId);
            this.notes[index] = {
                ...this.notes[index],
                title,
                content,
                tags,
                pinned: isPinned,
                updatedAt: new Date().toISOString()
            };
        } else {
            this.notes.push({
                id: Date.now().toString(),
                title,
                content,
                tags,
                pinned: isPinned,
                createdAt: new Date().toISOString(),
                updatedAt: new Date().toISOString()
            });
        }

        this.saveNotes();
        this.renderNotes();
        this.closeModal();
    }

    // Удаление заметки
    deleteNote(noteId) {
        if (confirm('Вы уверены, что хотите удалить эту заметку?')) {
            this.notes = this.notes.filter(n => n.id !== noteId);
            this.saveNotes();
            this.renderNotes();
        }
    }

    // Отображение заметок
    renderNotes() {
        const notesList = document.getElementById('notesList');

        if (this.notes.length === 0) {
            notesList.innerHTML = `
                <div class="empty-state">
                    <h3>Заметок пока нет</h3>
                    <p>Нажмите "Добавить заметку", чтобы создать первую</p>
                </div>
            `;
            return;
        }

        // Фильтрация по тегу
        const filterTag = document.getElementById('tagFilter').value.trim().toLowerCase();
        let filteredNotes = this.notes;
        if (filterTag) {
            filteredNotes = this.notes.filter(note =>
                note.tags.some(tag => tag.toLowerCase().includes(filterTag))
            );
        }

        // Разделение на закреплённые и обычные
        const pinned = [];
        const regular = [];
        filteredNotes.forEach(note => {
            if (note.pinned) pinned.push(note);
            else regular.push(note);
        });

        // Сортировка
        const sortFn = (a, b) => {
            const dateA = new Date(a.updatedAt);
            const dateB = new Date(b.updatedAt);
            return this.sortOrder === 'newest' ? dateB - dateA : dateA - dateB;
        };

        pinned.sort(sortFn);
        regular.sort(sortFn);
        const sortedNotes = [...pinned, ...regular];

        // Рендеринг
        notesList.innerHTML = '';
        sortedNotes.forEach(note => {
            const noteEl = document.createElement('div');
            noteEl.className = `note ${note.pinned ? 'pinned' : ''}`;
            noteEl.innerHTML = `
                <h3>${this.escapeHtml(note.title)}</h3>
                <div class="note-tags">
                    ${note.tags.length
                        ? note.tags.map(tag => `<span class="tag">${this.escapeHtml(tag)}</span>`).join('')
                        : '<em>без тегов</em>'}
                </div>
                <div class="note-date">
                    Создано: ${this.formatDate(note.createdAt)}<br>
                    Обновлено: ${this.formatDate(note.updatedAt)}
                </div>
                <div class="note-content">${this.escapeHtml(note.content)}</div>
                <div class="note-actions">
                    <button class="edit" data-id="${note.id}">✏️ Редактировать</button>
                    <button class="delete" data-id="${note.id}">🗑️ Удалить</button>
                </div>
            `;
            notesList.appendChild(noteEl);
        });

        // Обработчики кнопок
        document.querySelectorAll('.note-actions .edit').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.dataset.id;
                this.openModal(id);
            });
        });

        document.querySelectorAll('.note-actions .delete').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = e.target.dataset.id;
                this.deleteNote(id);
            });
        });
    }

    // Форматирование даты
    formatDate(dateString) {
        return new Date(dateString).toLocaleString('ru-RU', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    // Экранирование HTML
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Запуск приложения
document.addEventListener('DOMContentLoaded', () => {
    new NotesManager();
});