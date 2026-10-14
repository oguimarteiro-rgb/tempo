import Adw from 'gi://Adw';
import Gtk from 'gi://Gtk';
import {ExtensionPreferences} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

export default class TempoPrefs extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const settings = this.getSettings();
        const page = new Adw.PreferencesPage();
        const group = new Adw.PreferencesGroup({title: 'Atalho'});
        const row = new Adw.EntryRow({title: 'Abrir menu (ex.: <Super>t)'});
        row.set_text(settings.get_strv('atalho-menu')[0] ?? '');
        row.connect('changed', () => {
            const [ok] = Gtk.accelerator_parse(row.get_text());
            if (ok) settings.set_strv('atalho-menu', [row.get_text()]);
        });
        group.add(row);
        page.add(group);
        window.add(page);
    }
}
