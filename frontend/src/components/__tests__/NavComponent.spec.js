import { mount } from '@vue/test-utils';
import NavComponent from '../NavComponent.vue';

vi.mock('@/constants', () => ({
    IMAGES: {
        LOGO_SMALL: 'logo.png',
        FLAG_PALESTINE: 'flag.png',
    },
}));

vi.mock('../GameSearchComponent.vue', () => ({
    default: {
        name: 'GameSearchComponent',
        template: '<div class="game-search-stub" />',
    },
}));

const factory = () =>
    mount(NavComponent, {
        global: {
            stubs: {
                'router-link': {
                    template: '<a><slot /></a>',
                },
            },
        },
    });

describe('NavComponent', () => {
    it('toggles menu visibility when burger is clicked', async () => {
        const wrapper = factory();

        expect(wrapper.find('.navbar-menu').classes()).not.toContain('is-active');
        await wrapper.find('.navbar-burger').trigger('click');
        expect(wrapper.find('.navbar-menu').classes()).toContain('is-active');

        await wrapper.find('.navbar-menu').trigger('click');
        expect(wrapper.find('.navbar-menu').classes()).not.toContain('is-active');
    });

    it('renders images from constants', () => {
        const wrapper = factory();
        expect(wrapper.find('img').attributes('src')).toBe('logo.png');
        expect(
            wrapper.find('[title="Statement on Palestine"] img').attributes('src')
        ).toBe('flag.png');
    });
});
